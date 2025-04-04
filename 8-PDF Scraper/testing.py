import concurrent.futures
import time

timeout_duration = 2

def download_pdf():
    """Simulates a PDF download with a 5-second delay."""
    print("Starting download for: ")
    time.sleep(5)  # Simulate download time
    print("Finished download for: ")

def main():
    list1 = [1, 2, 3, 4, 5]

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(download_pdf) for _ in list1]

        while True:
            done, not_done = concurrent.futures.wait(futures, timeout=timeout_duration, return_when=concurrent.futures.FIRST_COMPLETED)

            # Process completed futures
            for future in done:
                if future.exception() is None:
                    print("Downloaded: ")
                else:
                    print(f"Error during download: {future.exception()}")
                futures.remove(future)  # Remove completed future from the list

            # If no futures are left, exit the loop
            if not futures:
                break

            # Optional: Add a short delay to avoid excessive polling
            time.sleep(0.1)

if __name__ == "__main__":
    main()
