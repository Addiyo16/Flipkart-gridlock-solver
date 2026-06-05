# download_grab_data.py - Download and unzip Grab AI for SEA Traffic Management dataset
import os
import urllib.request
import zipfile

def main():
    url = "https://s3-ap-southeast-1.amazonaws.com/grab-aiforsea-dataset/traffic-management.zip"
    dest_zip = r"C:\Users\ashok\.gemini\antigravity\scratch\traffic-management.zip"
    extract_dir = r"C:\Users\ashok\.gemini\antigravity\scratch\grab_traffic_data"
    
    print(f"Downloading from: {url}")
    print(f"To: {dest_zip}")
    
    try:
        # Define progress callback
        def progress_hook(block_num, block_size, total_size):
            downloaded = block_num * block_size
            if total_size > 0:
                percent = downloaded * 100 / total_size
                if block_num % 1000 == 0:
                    print(f"Downloaded: {downloaded / (1024*1024):.2f} MB ({percent:.2f}%)")
            else:
                if block_num % 1000 == 0:
                    print(f"Downloaded: {downloaded / (1024*1024):.2f} MB")
                    
        urllib.request.urlretrieve(url, dest_zip, progress_hook)
        print("Download completed successfully!")
        
        print(f"Extracting to: {extract_dir}")
        with zipfile.ZipFile(dest_zip, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        print("Extraction completed successfully!")
        
        # List contents of extract_dir
        print("Contents of extracted directory:")
        for root, dirs, files in os.walk(extract_dir):
            for f in files:
                path = os.path.join(root, f)
                print(f"  {path} (Size: {os.path.getsize(path) / (1024*1024):.2f} MB)")
                
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == '__main__':
    main()
