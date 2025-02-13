# Adjusted script to correctly parse the text file format
import re
import matplotlib.pyplot as plt
import pandas as pd

# Define the file path (update this as needed)
file_path = "../bg_result/readOnlyResult.txt"  # Update with the actual file path

# Read the file
with open(file_path, "r") as file:
    lines = file.readlines()

# Initialize lists to store extracted data
actions = []
threads = []
times = []

# Regular expressions to extract relevant data
experiment_pattern = re.compile(r"threads=(\d+), expected actions=(\d+)")
result_pattern = re.compile(r"Result: (\d+) sec: (\d+) actions")

# Parse the file
current_threads = None
current_actions = None

for line in lines:
    experiment_match = experiment_pattern.search(line)
    result_match = result_pattern.search(line)

    if experiment_match:
        # Store the latest threads and actions count found
        current_threads = int(experiment_match.group(1))
        current_actions = int(experiment_match.group(2))

    if result_match and current_threads is not None and current_actions is not None:
        # Store the extracted results
        execution_time = int(result_match.group(1))

        threads.append(current_threads)
        actions.append(current_actions)
        times.append(execution_time)

        # Reset after storing the result
        current_threads = None
        current_actions = None

# Convert extracted data into a DataFrame
df = pd.DataFrame({"actions": actions, "threads": threads, "times": times})

# Extract unique action values
unique_actions = sorted(df["actions"].unique())

# Create the line chart
fig, ax = plt.subplots(figsize=(8, 6))

# Plot each action set separately
for action in unique_actions:
    subset = df[df["actions"] == action]
    ax.plot(subset["threads"], subset["times"], marker='o', label=f"Actions={action:,}")

# Labeling the chart
ax.set_xscale("log")
ax.set_yscale("log")
ax.set_xlabel("Threads (log scale)")
ax.set_ylabel("Execution Time (sec) (log scale)")
ax.set_title("Execution Time vs. Threads for Different Action Counts")
ax.legend()
ax.grid(True, which="both", linestyle="--", linewidth=0.5)

# Show the plot
plt.savefig("../bg_result/pics/readOnlyResult.png", dpi=300, bbox_inches="tight")
plt.show()

