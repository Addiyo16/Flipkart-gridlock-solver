# parse_pb.py - Search for byte patterns in .pb Protobuf session file
def main():
    pb_path = r"C:\Users\ashok\.gemini\antigravity\conversations\9a68881f-9f42-497a-9b69-5e622236c737.pb"
    with open(pb_path, 'rb') as f:
        data = f.read()
    
    print(f"File length: {len(data)}")
    
    # Let's search for some strings
    targets = [b'decode_geohash', b'LGBMRegressor', b'train.py', b'submission.csv', b'CatBoostRegressor']
    for t in targets:
        pos = data.find(t)
        print(f"Position of '{t.decode()}': {pos}")
        
    # If we found any target, let's print the surrounding bytes
    pos = data.find(b'decode_geohash')
    if pos != -1:
        # print 500 bytes around it
        start = max(0, pos - 200)
        end = min(len(data), pos + 1000)
        snippet = data[start:end]
        print(f"\nSnippet around decode_geohash:\n{repr(snippet[:300])}")
        
        # Let's write a simple algorithm to extract the full text block containing decode_geohash
        # Printable ASCII is between 32 and 126, plus newline (10, 13) and tab (9)
        # We can expand from 'pos' left and right as long as bytes are printable or whitespace
        left = pos
        while left > 0 and (32 <= data[left-1] <= 126 or data[left-1] in [9, 10, 13]):
            left -= 1
        right = pos
        while right < len(data) and (32 <= data[right] <= 126 or data[right] in [9, 10, 13]):
            right += 1
            
        print(f"\nExtracted block length: {right - left}")
        print(f"Extracted block:\n{data[left:right].decode('utf-8', errors='ignore')[:500]}")

if __name__ == '__main__':
    main()
