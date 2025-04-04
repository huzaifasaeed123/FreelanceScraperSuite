# Define the file paths
file1_path = "extracted_urls.txt"
file2_path = "extracted_urls2.txt"
output_file_path = "MegaMissing.txt"

# Read the URLs from the first file
with open(file1_path, 'r') as file1:
    urls_file1 = file1.read().splitlines()

# Read the URLs from the second file and store them in a set for fast lookup
with open(file2_path, 'r') as file2:
    urls_file2 = set(file2.read().splitlines())

print(f"Total URLs in file1: {len(urls_file1)}")
print(f"Total URLs in file2: {len(urls_file2)}")

# Find URLs that are in the first file but not in the second file
missing_urls = [url for url in urls_file1 if url not in urls_file2]

# Write the missing URLs to a new file
with open(output_file_path, 'w') as output_file:
    for url in missing_urls:
        output_file.write(url + '\n')

print(f"Comparison complete. Missing URLs are saved to {output_file_path}.")
