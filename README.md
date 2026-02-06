# Interactive Table Visualiser (GUI)

A beginner-friendly Python GUI for exploring **tab-separated tables** (optionally `.gz`) by:
- previewing the dataset,
- selecting an **ID column**,
- selecting multiple **Row IDs** (checkboxes),
- creating your own **groups** (each group = chosen sample/value columns),
- plotting **Box + Jitter** where:
  - **X-axis = groups**
  - **colors = sample columns**
  - **marker shapes = Row IDs**
  - **two legends** (samples/colors + Row IDs/shapes)

This project is written in a clear, beginner-friendly style.

---

## Dataset Format (Expected)

Your dataset should be a **tab-separated file** (`.tab`, `.tsv`, `.txt`), optionally compressed as `.gz`.

### Required structure
- **One ID column** (row identifier), e.g. `gene`, `id`, `name`, etc.
- **Many numeric columns** (samples / measurements)

Example:

    ID      Sample_A  Sample_B  Sample_C
    Row1    10.2      9.8       11.0
    Row2    5.1       5.0       5.3

---

## Features

1. Load any tab-separated dataset (`.tab/.tsv/.txt/.gz`)
2. Preview the dataset before plotting
3. Select Row IDs using checkboxes
4. Create custom groups and assign sample columns to each group
5. Plot **Box + Jitter**
   - Groups on X-axis
   - Samples = colors
   - Row IDs = marker shapes
   - Two legends (colors + shapes)
6. Save plot as PNG
7. Export group definitions

---

## Installation

### Install dependencies
  
    pip install  pandas
    pip install  numpy
    pip install  matplotlib

Note:
- `tkinter` is included with most Python installations.
- On Linux, you may need:

    sudo apt install python3-tk

---

## Run the Application

From the project directory:

    python Visualiser_GUI.py

---

## Example: Using the GSE112627 Dataset

Dataset name:

    GSE112627_Normalized_counts_file_on_ALL_groups.tab.gz

### Step 1 — Download the dataset 

1) Go to the GEO page for **GSE112627**
2) https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE112627  
3) In **Series supplementary files**, download:

    GSE112627_Normalized_counts_file_on_ALL_groups.tab.gz

4) Put it next to `Visualiser_GUI.py` (recommended), for example:

    interactive-table-visualiser/
    ├─ Visualiser_GUI.py
    └─ data/
       └─ GSE112627_Normalized_counts_file_on_ALL_groups.tab.gz

---


### Step 2 — Open in the GUI

Run:

    python Visualiser_GUI.py

Then:
1) Click **Select Dataset File**
2) Choose `GSE112627_Normalized_counts_file_on_ALL_groups.tab.gz`
3) Click **Preview Dataset**

---

### Step 3 — Select the ID column

For this dataset, the ID column is often:

    Unnamed: 0

Select it from the **ID column** dropdown.

---

### Step 4 — Select Row IDs

Use the search box and checkboxes.

Example Row IDs:
- Scn1a
- Gad1
- Gad2
- Slc6a1

---

### Step 5 — Create groups (example)

Based on column names:

- WT: select columns containing `_WT`
- KO: select columns containing `_KO`
- KO_Sz (optional): select columns containing `_KO_Sz`

---

### Step 6 — Plot

Click:

    Plot Box + Jitter

You will see:
- Groups on the X-axis
- Colored points = samples
- Marker shapes = Row IDs
- Two legends on the right side


