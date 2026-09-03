import statistics


def analyze_consecutive_occurrences(file_path, substring):
    """
    Analyzes the consecutive occurrences of a substring in each line of a file.

    Parameters:
        file_path (str): Path to the file to be read.
        substring (str): Substring to count consecutive occurrences of.

    Prints:
        Average count, median count, and highest count of consecutive occurrences.
    """
    consecutive_counts = []

    with open(file_path, "r") as file:
        for line in file:
            line = line.strip()  # Remove leading/trailing whitespace
            max_consecutive = 0
            current_count = 0

            # Iterate through the line to find consecutive occurrences
            i = 0
            while i <= len(line) - len(substring):
                if line[i : i + len(substring)] == substring:
                    current_count += 1
                    i += len(substring)  # Move past the substring
                else:
                    max_consecutive = max(max_consecutive, current_count)
                    current_count = 0
                    i += 1

            # Update the max for the last sequence in the line
            max_consecutive = max(max_consecutive, current_count)
            consecutive_counts.append(max_consecutive)

    # Calculate average, median, and high count
    if consecutive_counts:
        average_count = sum(consecutive_counts) / len(consecutive_counts)
        median_count = statistics.median(consecutive_counts)
        high_count = max(consecutive_counts)

        print(f"Average Count: {average_count}")
        print(f"Median Count: {median_count}")
        print(f"High Count: {high_count}")
    else:
        print("No data found in file.")


# Example usage
# Replace 'input.txt' with the path to your file and 'abc' with your desired substring
analyze_consecutive_occurrences("MapTasker.html", "&nbsp;")
