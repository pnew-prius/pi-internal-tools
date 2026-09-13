"""
Extract and print the KML file from inside a zip blob using range requests.
"""
import struct, sys, io, zipfile
from azure.identity import AzureCliCredential
from azure.storage.blob import BlobClient

ACCOUNT   = "piimageprocessing"
CONTAINER = "tobeprocessed"

def get_client(blob_name):
    cred = AzureCliCredential()
    url  = f"https://{ACCOUNT}.blob.core.windows.net/{CONTAINER}/{blob_name}"
    return BlobClient.from_blob_url(url, credential=cred)

def range_bytes(client, start, length):
    stream = client.download_blob(offset=start, length=length)
    return stream.readall()

def find_local_file(client, blob_size, target_name):
    """Find a specific file in the zip and return its compressed data."""
    # Read tail to find EOCD / ZIP64
    tail_size = min(65536, blob_size)
    tail = range_bytes(client, blob_size - tail_size, tail_size)

    cd_offset = cd_size = None

    zip64_loc = b'\x50\x4b\x06\x07'
    idx64 = tail.rfind(zip64_loc)
    if idx64 != -1:
        eocd64_off = struct.unpack_from('<Q', tail, idx64 + 8)[0]
        eocd64 = range_bytes(client, eocd64_off, 56)
        cd_size   = struct.unpack_from('<Q', eocd64, 40)[0]
        cd_offset = struct.unpack_from('<Q', eocd64, 48)[0]
    else:
        eocd_sig = b'\x50\x4b\x05\x06'
        idx = tail.rfind(eocd_sig)
        if idx == -1:
            raise RuntimeError("EOCD not found")
        eocd = tail[idx:]
        cd_size   = struct.unpack_from('<I', eocd, 12)[0]
        cd_offset = struct.unpack_from('<I', eocd, 16)[0]

    cd = range_bytes(client, cd_offset, cd_size)

    # Find target file in central directory
    pos = 0
    sig = b'\x50\x4b\x01\x02'
    while pos <= len(cd) - 46:
        if cd[pos:pos+4] != sig:
            pos += 1
            continue
        comp_method = struct.unpack_from('<H', cd, pos + 10)[0]
        comp_size   = struct.unpack_from('<I', cd, pos + 20)[0]
        local_hdr   = struct.unpack_from('<I', cd, pos + 42)[0]
        fname_len   = struct.unpack_from('<H', cd, pos + 28)[0]
        extra_len   = struct.unpack_from('<H', cd, pos + 30)[0]
        comment_len = struct.unpack_from('<H', cd, pos + 32)[0]
        fname = cd[pos+46:pos+46+fname_len].decode('utf-8', errors='replace')

        # Handle ZIP64 extra fields for large offsets
        if local_hdr == 0xFFFFFFFF:
            extra_start = pos + 46 + fname_len
            extra_data  = cd[extra_start : extra_start + extra_len]
            ep = 0
            while ep < len(extra_data) - 4:
                hid  = struct.unpack_from('<H', extra_data, ep)[0]
                hlen = struct.unpack_from('<H', extra_data, ep+2)[0]
                if hid == 0x0001:
                    local_hdr = struct.unpack_from('<Q', extra_data, ep+4)[0]
                    break
                ep += 4 + hlen

        if fname == target_name or fname.endswith("/" + target_name):
            print(f"Found '{fname}' at local header offset {local_hdr:,}, compressed size {comp_size:,}, method {comp_method}")
            # Read local file header to find data offset
            lhdr = range_bytes(client, local_hdr, 30)
            lf_name_len  = struct.unpack_from('<H', lhdr, 26)[0]
            lf_extra_len = struct.unpack_from('<H', lhdr, 28)[0]
            data_offset  = local_hdr + 30 + lf_name_len + lf_extra_len
            comp_data    = range_bytes(client, data_offset, comp_size)
            if comp_method == 0:
                return comp_data  # stored, no compression
            elif comp_method == 8:
                import zlib
                return zlib.decompress(comp_data, -15)
            else:
                raise RuntimeError(f"Unsupported compression method: {comp_method}")

        pos += 46 + fname_len + extra_len + comment_len

    raise RuntimeError(f"File '{target_name}' not found in zip")

if __name__ == "__main__":
    blob_name   = sys.argv[1] if len(sys.argv) > 1 else "cpd26-46.zip"
    target_file = sys.argv[2] if len(sys.argv) > 2 else "46.kml"

    client = get_client(blob_name)
    props  = client.get_blob_properties()

    data = find_local_file(client, props.size, target_file)
    print("\n--- File contents ---")
    print(data.decode('utf-8', errors='replace'))
