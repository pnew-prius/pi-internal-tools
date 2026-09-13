"""
Read the central directory of a zip in Azure Blob Storage using range requests.
No full download needed — reads only the last ~64KB (zip central directory).
"""
import struct, sys
from azure.identity import AzureCliCredential
from azure.storage.blob import BlobClient

ACCOUNT = "piimageprocessing"
CONTAINER = "tobeprocessed"
IMG_EXTS = {"jpg","jpeg","tif","tiff","jp2","png","cr2","raw","nef","dng"}

def get_blob_client(blob_name):
    cred = AzureCliCredential()
    url  = f"https://{ACCOUNT}.blob.core.windows.net/{CONTAINER}/{blob_name}"
    return BlobClient.from_blob_url(url, credential=cred)

def range_bytes(client, start, end):
    stream = client.download_blob(offset=start, length=(end - start + 1))
    return stream.readall()

def list_zip_contents(blob_name):
    client = get_blob_client(blob_name)
    props  = client.get_blob_properties()
    size   = props.size
    print(f"Blob: {blob_name}  Size: {size:,} bytes ({size/1e9:.2f} GB)")

    # Read last 64KB to locate End of Central Directory
    tail_size = min(65536, size)
    tail = range_bytes(client, size - tail_size, size - 1)

    # Try regular EOCD first
    eocd_sig = b'\x50\x4b\x05\x06'
    idx = tail.rfind(eocd_sig)

    cd_offset = None
    cd_size   = None
    num_entries = None

    if idx != -1:
        eocd = tail[idx:]
        ne   = struct.unpack_from('<H', eocd, 10)[0]
        cs   = struct.unpack_from('<I', eocd, 12)[0]
        co   = struct.unpack_from('<I', eocd, 16)[0]
        if co != 0xFFFFFFFF and cs != 0xFFFFFFFF:
            num_entries = ne
            cd_size     = cs
            cd_offset   = co

    if cd_offset is None:
        # ZIP64
        zip64_loc = b'\x50\x4b\x06\x07'
        idx64 = tail.rfind(zip64_loc)
        if idx64 == -1:
            raise RuntimeError("Cannot locate EOCD or ZIP64 locator")
        eocd64_offset = struct.unpack_from('<Q', tail, idx64 + 8)[0]
        eocd64 = range_bytes(client, eocd64_offset, eocd64_offset + 56 - 1)
        num_entries = struct.unpack_from('<Q', eocd64, 32)[0]
        cd_size     = struct.unpack_from('<Q', eocd64, 40)[0]
        cd_offset   = struct.unpack_from('<Q', eocd64, 48)[0]
        print(f"ZIP64 format: {num_entries} entries")
    else:
        print(f"ZIP32 format: {num_entries} entries")

    print(f"Downloading central directory ({cd_size/1e6:.1f} MB)...")
    cd = range_bytes(client, cd_offset, cd_offset + cd_size - 1)

    files = []
    pos   = 0
    sig   = b'\x50\x4b\x01\x02'
    while pos <= len(cd) - 46:
        if cd[pos:pos+4] != sig:
            pos += 1
            continue
        fname_len   = struct.unpack_from('<H', cd, pos + 28)[0]
        extra_len   = struct.unpack_from('<H', cd, pos + 30)[0]
        comment_len = struct.unpack_from('<H', cd, pos + 32)[0]
        uncomp_size = struct.unpack_from('<I', cd, pos + 24)[0]
        fname = cd[pos+46 : pos+46+fname_len].decode('utf-8', errors='replace')
        files.append({"name": fname, "size": uncomp_size})
        pos += 46 + fname_len + extra_len + comment_len

    return files

def summarize(files):
    from collections import Counter
    exts = Counter()
    for f in files:
        parts = f["name"].rsplit(".", 1)
        ext = parts[-1].lower() if len(parts) > 1 else "(none)"
        exts[ext] += 1

    print(f"\nTotal entries in zip: {len(files)}")
    print("\nFile types:")
    for ext, count in exts.most_common():
        print(f"  .{ext:12s} {count:5d}")

    kmls = [f for f in files if f["name"].lower().endswith(".kml")]
    print(f"\nKML files ({len(kmls)}):")
    for k in kmls:
        print(f"  {k['name']}  ({k['size']:,} bytes)")

    imgs = [f for f in files if f["name"].rsplit(".",1)[-1].lower() in IMG_EXTS]
    print(f"\nImage files: {len(imgs)}")
    for i in imgs[:15]:
        print(f"  {i['name']}")
    if len(imgs) > 15:
        print(f"  ... and {len(imgs)-15} more")

if __name__ == "__main__":
    blob = sys.argv[1] if len(sys.argv) > 1 else "cpd26-46.zip"
    files = list_zip_contents(blob)
    summarize(files)
