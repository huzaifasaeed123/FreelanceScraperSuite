# Define file paths (adjust as needed)
file1_path = 'file1.txt'
file2_path = 'file2.txt'
output_path = 'unmatched_urls.txt'

# Step 1: Read the URLs from both files and store them in lists
def read_file_to_list(file_path):
    with open(file_path, 'r') as f:
        return [line.strip() for line in f.readlines()]

# Step 2: Store the URLs from file2 in a dictionary for fast lookup
def list_to_dict(url_list):
    return {url: True for url in url_list}

# Step 3: Compare the URLs from file1 with the dictionary from file2
def find_unmatched_urls(file1_urls, file2_dict):
    unmatched_urls = []
    for url in file1_urls:
        if url not in file2_dict:
            print("hi")
            unmatched_urls.append(url)
    return unmatched_urls

# Step 4: Write the unmatched URLs to a new text file
def write_list_to_file(url_list, output_file):
    with open(output_file, 'w') as f:
        for url in url_list:
            f.write(f"{url}\n")

# Main process
file1_urls = read_file_to_list(file2_path)
file2_urls = read_file_to_list(file1_path)
print(len(file1_urls))
print(len(file2_urls))
# Convert file2 URLs to a dictionary for fast lookup
file2_dict = list_to_dict(file2_urls)

# Find unmatched URLs from file1
unmatched_urls = find_unmatched_urls(file1_urls, file2_urls)

# Write unmatched URLs to a new file
write_list_to_file(unmatched_urls, output_path)

print(f"Unmatched URLs written to {output_path}")
