def analyze_substring_occurrences(filename, substring):
    """
    Reads a file of text, finds the substring, and calculates
    average, median, low, and high number of consecutive occurrences
    of the substring in each line.

    Args:
        filename: Path to the text file.
        substring: The substring to search for.

    Returns:
        A tuple containing:
            - average occurrences
            - median occurrences
            - lowest occurrences
            - highest occurrences
    """
    try:
        with open(filename, "r") as file:
            lines = file.readlines()

        occurrences_per_line = []
        for line in lines:
            current_count = 0
            max_count = 0
            for i in range(len(line) - len(substring) + 1):
                if line[i : i + len(substring)] == substring:
                    current_count = 1
                    while (
                        i + len(substring) < len(line)
                        and line[i + len(substring) : i + 2 * len(substring)] == substring
                    ):
                        current_count += 1
                        i += len(substring)
                    max_count = max(max_count, current_count)
            occurrences_per_line.append(max_count)

        average = sum(occurrences_per_line) / len(occurrences_per_line)
        occurrences_per_line.sort()
        median = occurrences_per_line[len(occurrences_per_line) // 2]
        low = occurrences_per_line[0]
        high = occurrences_per_line[-1]

        return average, median, low, high

    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
        return None


# Example usage
filename = "MapTasker.html"  # Replace with the actual filename
substring = "&nbsp;"  # Replace with the substring to search for

results = analyze_substring_occurrences(filename, substring)

if results:
    average, median, low, high = results
    print(f"Average consecutive occurrences: {average:.2f}")
    print(f"Median consecutive occurrences: {median}")
    print(f"Lowest consecutive occurrences: {low}")
    print(f"Highest consecutive occurrences: {high}")
