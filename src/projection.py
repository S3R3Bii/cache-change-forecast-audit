"""Use opaque object bytes, never the future-access field."""
def project(raw,expected_records):
    if len(raw)!=expected_records*24:raise ValueError('incomplete fixed request prefix')
    mapping={};ids=[];clocks=[];zero_size=ties=regressions=0
    previous=None
    for i in range(expected_records):
        record=memoryview(raw)[i*24:(i+1)*24]
        clock=int.from_bytes(record[:4],'little')
        token=bytes(record[4:12])
        size=int.from_bytes(record[12:16],'little')
        # Bytes16:24 contain future access; no part of the projection reads them.
        if token not in mapping:mapping[token]=len(mapping)
        ids.append(mapping[token]);clocks.append(clock);zero_size+=int(size==0)
        if previous is not None:
            ties+=int(clock==previous);regressions+=int(clock<previous)
        previous=clock
    return ids,dict(records=len(ids),distinct_prefix_ids=len(mapping),first_raw_clock=clocks[0],last_raw_clock=clocks[-1],clock_ties=ties,clock_regressions=regressions,zero_size_records=zero_size,clock_size_interpretation='little-endian working metadata; no asserted calendar-time unit',future_field_decoded=False,forecast_identity='Opaque bytes4:12, ordinal by first appearance; invariant to bijective re-encoding')
def decode_prefix(path,n):
    import zstandard
    with path.open('rb') as file,zstandard.ZstdDecompressor().stream_reader(file) as reader:raw=reader.read(n*24)
    return raw
