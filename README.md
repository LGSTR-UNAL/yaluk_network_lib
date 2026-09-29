# yaluk_network_lib

Python library for modelling overhead electrical distribution networks and generating
simulation cases for **ATP/EMTP** coupled with the **YALUK** FDTD model for
lightning-induced overvoltages.

Starting from a tabular description of a network (nodes, lines, conductors, line
geometries, transformers and surge arresters), the library builds an object model of the
network, computes line parameters, and writes all the input files needed to simulate
direct and indirect (induced) lightning strikes: the ATP case (`.atp`), LCC/JMarti line
models, YALUK line geometry files, lightning current files and project configuration
files. It also includes a Monte Carlo lightning generator, direct/indirect strike
classification, an ATP solver runner and plotting utilities.

---

## Table of contents

- [Capabilities](#capabilities)
- [Requirements](#requirements)
- [Installation](#installation)
- [Package layout](#package-layout)
- [Quick start](#quick-start)
- [Input data format](#input-data-format)
- [Generated files](#generated-files)
- [Lightning modelling](#lightning-modelling)
- [Running the ATP solver](#running-the-atp-solver)
- [Plotting](#plotting)
- [Units and conventions](#units-and-conventions)
- [Testing](#testing)
- [License](#license)

---

## Capabilities

### Network modelling (`Network_lib`)
- **Network object model**: `Network`, `Node`, `Line`, `Conductor`,
  `Configuration_Type`, `Transformer`, `SurgeArrester` and lumped RLC shunt elements
  (`Shunt_lump`, `lumped_element`).
- **Building from data**: `network_setting()` builds a full network from `pandas`
  DataFrames, and `network_setting_csv()` builds one from CSV files. Both check the
  input: missing files, wrong extensions, malformed geometry literals and references to
  unknown conductors all raise an error.
- **Conductor catalogue and line configurations**: `build_conductors_db()` and
  `build_configurations_db()` turn a cable catalogue and line geometries into reusable
  objects. Each line references a configuration by id.
- **Multi-conductor lines**: from 1 to 5 conductors per line. Phases are assigned in the
  order `A, B, C, N, M`. For 5-conductor lines, `N` and `M` are bonded with a 1 µΩ
  resistance.
- **Line parameters**: per-unit-length inductance `Lm`, capacitance `Cm` and
  characteristic impedance matrix `Zc` computed from conductor heights, horizontal
  positions and radii (`Configuration_Type.gen_parameters()`).
- **Topology handling**:
  - Nodes that fall within 10 cm of an existing node are merged.
  - Duplicate lines between the same pair of nodes are rejected, in either direction.
  - A low-voltage node is created automatically for every transformer.
- **Transformers**: high-frequency capacitive model of a two-winding transformer
  (HV–ground, LV–ground and HV–LV capacitances plus grounding resistance), connected
  single-, two- or three-phase.
- **Surge arresters**: connected per phase using ATP `.pch` punch files.
- **Georeferencing**: coordinate conversion between WGS84 (EPSG:4326) and a projected
  CRS (default EPSG:9377, MAGNA-SIRGAS *Origen Nacional*, Colombia) via `pyproj`. Every
  node and lightning point carries both X/Y and latitude/longitude.
- **Export**: `create_dataframes()` exports nodes and lines to DataFrames
  (`df_nodes`, `df_lines`) for analysis and plotting.

### Simulation file generation
- **ATP case file** (`MakeAtpFile` / `MakeATPBuffer`):
  - Header, MODELS section, branches, sources and output requests.
  - For **indirect strikes**, it writes the `Yaluk<n>` MODELS that link each illuminated
    line to the YALUK DLL (`FOREIGN YALUK_DLL_MODEL`).
  - For **direct strikes**, it injects the lightning current source at the struck line.
  - `AtpSettings` sets print/plot frequency, `.pl4` output, phasor and max/min output,
    and memory saving.
- **LCC / JMarti line models** (`MakeLccFile`): writes the `.dat` and `.dbm` files for
  each line and, optionally, runs the solver to produce `.pch` and `.lib` files. It can
  also return the `.lib` files as a ZIP buffer.
- **YALUK line geometry files** (`MakeLineFiles`): writes `CaseFiles/linea_###.txt` for
  each line, either to disk or as an in-memory ZIP.
- **Project files** (`Project_lib`): `yaluk.ini`, `yaluk_status.ini` and
  `CaseFiles/miscelaneo.txt` (channel, soil and FDTD settings), plus the one-call
  `create_project_files()`.
- **In-memory mode**: most writers can return `BytesIO`/`StringIO` buffers instead of
  writing to disk. This is useful for cluster or web back-ends.

### Lightning (`Lightning_lib`)
- **Individual strokes** (`Lightning`): Heidler waveform with a first and optional
  second function (`Ih`, `tf`, `tc`, `n`), plus the strike location. Writes
  `corr_#####.txt` files.
- **Monte Carlo generation** (`Lightning_stat`):
  - Draws random peak currents and front times from lognormal distributions, with the
    two correlated.
  - Places strike points uniformly over the network's bounding box plus a configurable
    margin.
- **Strike classification** (`Network.check_direct_strike`):
  - Uses the electrogeometric model (striking distance `Rs = 10·I^0.65`) to separate
    direct from indirect strikes.
  - Gives the minimum distance to the network and the nearest line.
  - For indirect strikes, estimates the maximum induced voltage with a simplified Rusck
    formula.
  - Marks the lines within a distance threshold for FDTD (YALUK) coupling.
- **Export**: writes results to a `;`-separated CSV database, a text buffer, or a
  DataFrame that includes latitude/longitude.
- **Channel and soil settings**: `LightningChannel` (TL/MTL model, return-stroke
  velocity, channel height, attenuation constant) and `Soil` (conductivity, permittivity,
  perfect-ground flag).

### Solver integration (`Network_lib.atp_solver`)
- `run_atp_file()` / `run_atp_solver()` run ATP/YALUK on `.atp`, `.dat` and `.dbm`
  files.
  - The executable is found from, in order: an explicit path, the `SOLVER_PATH`
    environment variable, the Windows default location, then `PATH`.
  - The ATP runtime files are copied into the working directory when needed.
  - On failure, the error message includes stdout, stderr and the tail of the `.lis`
    file.
- `check_required_output()` checks that an output file exists and is not empty.
  `cleanup_solver_files()` deletes temporary solver files.

### Plotting (`plot_lib`)
- `plot_nodes`, `plot_lines`, `plot_lightnings`: network and strike-point maps in
  Cartesian or geographic coordinates.
- `plot_stat` helpers for post-processing results: voltage-bin tables, exceedance across
  nodes, per-node histograms and failure-rate curves.

---

## Requirements

### Python
- **Python ≥ 3.12**. The code uses PEP 701 f-strings (quotes nested inside f-strings),
  `match` statements and `X | Y` type unions.

### Python packages

| Package      | Used for                                                          |
|--------------|-------------------------------------------------------------------|
| `numpy`      | Line parameter matrices, geometry                                 |
| `pandas`     | Input tables, CSV I/O, result DataFrames                          |
| `scipy`      | Lognormal distributions for Monte Carlo lightning (`scipy.stats`) |
| `pyproj`     | WGS84 ↔ projected coordinate transformations                      |
| `matplotlib` | Plotting (`plot_lib`)                                             |
| `seaborn`    | Plot styling (`plot_lib`)                                         |
| `pytest`     | Test suite (development only)                                     |

The sub-packages are imported separately, so `scipy` and `matplotlib` are only needed
when you use `Lightning_lib.Lightning_stat` or `plot_lib`. `pyproj` is always required,
because `Network` uses it when it is created.

### External software (for simulation)
Generating files needs only Python. To **run** simulations, or to build the LCC `.lib`
files with `MakeLccFile(run_solver=True)`, you also need:

> **ATP and libyaluk are not included in this repository.** Each user must supply their
> own copy of both:
>
> - **ATP (Alternative Transients Program)**: ATP is licensed software, available free
>   of charge to registered users. Get it by registering with an ATP user group; see
>   [www.emtp.org](https://www.emtp.org) and the European EMTP-ATP Users Group
>   ([www.eeug.org](https://www.eeug.org)).
> - **libyaluk**: the YALUK FDTD library that ATP calls to compute lightning-induced
>   voltages. Source code:
>   [github.com/LGSTR-UNAL/libyaluk](https://github.com/LGSTR-UNAL/libyaluk).
>
> Build or link ATP against libyaluk to get the solver executable described below.

- An **ATP solver build with the YALUK extension**:
  - Windows: `tp_yaluk.exe`, looked for by default in `C:\EMTP\Solver\`.
  - Linux: `tpyaluk` on `PATH`.
- The ATP runtime files next to the executable: `startup`, `startup.big`, `startup.gig`,
  `graphics`, `graphics.aux`, `graphics.std`, `blockd51.bin`, and the compiled
  libyaluk library:
  - Windows: `Atp_Yaluk_lib.dll`.
  - Linux: get the library from the
    [libyaluk repository](https://github.com/LGSTR-UNAL/libyaluk).
- The surge arrester `.pch` files, placed in a `surges/` directory relative to where the
  ATP case runs. `notebooks/surges.zip` has examples.

Without the solver, use `MakeLccFile(run_solver=False)`. The `.dat`/`.dbm` files are
still written.

---

## Installation

The package is imported as `yaluk_network_lib`, so the repository directory must keep
that name and its **parent directory** must be on `sys.path`.

```bash
git clone <repo-url> yaluk_network_lib
cd yaluk_network_lib
python3.12 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install numpy pandas scipy pyproj matplotlib seaborn pytest
```

To use it from another project, add the parent directory to the path:

```bash
export PYTHONPATH="/path/to/parent_of_repo:$PYTHONPATH"
```

or, in Python:

```python
import sys; sys.path.insert(0, "/path/to/parent_of_repo")
import yaluk_network_lib.Network_lib as nl
```

---

## Package layout

```
yaluk_network_lib/
├── Network_lib/          # Core network model and ATP/LCC writers
│   ├── Network.py        # Network class: nodes, lines, transformers, file generation
│   ├── Node.py, Line.py, Conductor.py, Configuration_Type.py
│   ├── Transformer.py, SurgeArrester.py, Shunt_element.py
│   ├── net_setting.py    # network_setting(), network_setting_csv(), catalogue builders
│   ├── ATP_cards_w.py    # ATP card writers (header, models, branches, sources, output)
│   ├── LCC_cards.py      # LCC/JMarti card writers
│   ├── basic_func.py     # Line parameters and numerical helpers
│   ├── GeoTransform.py   # CoordTransf, PointXY, PointLatLng
│   └── atp_solver.py     # Solver discovery and execution
├── Lightning_lib/        # Lightning, Lightning_stat, LightningChannel, Soil
├── Project_lib/          # ProjectSettings, SimulationSettings, project-file writers
├── plot_lib/             # plotylk (maps), plot_stat (statistics)
├── examples/example.py   # Script example
├── notebooks/            # Jupyter examples (example_nb.ipynb) and sample data
└── tests/                # pytest suite
```

---

## Quick start

```python
import pandas as pd
import yaluk_network_lib.Network_lib as nl
import yaluk_network_lib.Project_lib as yp
from yaluk_network_lib.Lightning_lib import Lightning, Lightning_stat

# 1. Input tables (see "Input data format")
Nodes = pd.DataFrame(
    [[1, "N1", 125300, 103000], [2, "N2", 125450, 103050], [3, "N3", 125500, 103100]],
    columns=["id", "label", "y", "x"],
)
Lines = pd.DataFrame(
    [[1, "L1", "N1", "N2", "Config_A"], [2, "L2", "N2", "N3", "Config_A"]],
    columns=["id", "label", "from_node", "to_node", "configuration_type"],
)
Cables = pd.DataFrame(
    [["ACSR_2/0", "Cable ACSR 2/0", 0.005, 1.0, "ACSR 2/0 conductor"]],
    columns=["id", "label", "radio", "resistance", "description"],
)
Config_types = pd.DataFrame(
    [["Config_A", "Three-phase", "3 conductors at 10 m",
      "[('ACSR_2/0',10,0), ('ACSR_2/0',10,2), ('ACSR_2/0',10,4)]"]],
    columns=["id", "name", "description", "Geometry"],
)
Transformers = pd.DataFrame(
    [[1, "T1", "N2", 111, "Tr1"]],
    columns=["id", "label", "from_node", "phases", "trf_type"],
)
Trftype = pd.DataFrame(
    [["Tr1", 340e-12, 215e-12, 744e-12, 10.0]],
    columns=["id", "CHV", "CLV", "CHL", "ground"],
)
Surge_Arresters = pd.DataFrame(
    [[1, "SA1", "N2", 111, "SAIEEE_3ph.pch"]],
    columns=["id", "label", "node", "phases", "file"],
)

# 2. Build the network
net = nl.network_setting(Nodes, Lines, Transformers, Surge_Arresters,
                         Trftype, Cables, Config_types, name_net="Example_Network")

# 3. Define a stroke (coordinates relative to the network origin, in m)
stroke = Lightning()
stroke.X_location, stroke.Y_location = 100.0, 20.0
stroke.Ih1, stroke.tf1, stroke.tc1, stroke.n1 = 40e3, 2e-6, 5e-5, 2

# 4. Generate simulation files
net.MakeAtpFile(stroke=stroke)             # Example_Network/Example_Network.atp
net.MakeLccFile(run_solver=False)          # Example_Network/lcc/lcc_###.dat/.dbm
net.MakeLineFiles(return_buffer=False)     # Example_Network/CaseFiles/linea_###.txt

# 5. Monte Carlo lightning database
stats = Lightning_stat(net, num_events=1000, M="ProbDistribution")
stats.Create_csvDB("lightning_database.csv")
df = stats.create_dataframe()
```

For the whole workflow in one call (misc file, `yaluk.ini`, stroke file, ATP case, LCC
with solver, and line files):

```python
settings = yp.ProjectSettings()     # or yp.setup_settings(sim_df, channel_df, soil_df, atp_df)
yp.create_project_files(settings, net, stroke,
                        solver_cwd=r"C:\EMTP\Solver",
                        solver_path=r"C:\EMTP\Solver\tp_yaluk.exe")
```

See [examples/example.py](examples/example.py) and
[notebooks/example_nb.ipynb](notebooks/example_nb.ipynb) for complete examples.

---

## Input data format

`network_setting()` takes seven DataFrames. `network_setting_csv()` takes the paths of
seven CSV files with the same columns.

| Table             | Columns                                                  | Notes |
|-------------------|----------------------------------------------------------|-------|
| `Nodes`           | `id`, `label`, `x`, `y`                                  | `x`/`y` are absolute projected coordinates (m). `id` is an integer or a string of at most 4 characters. |
| `Lines`           | `id`, `label`, `from_node`, `to_node`, `configuration_type` | `from_node`/`to_node` are node **labels**. `configuration_type` is a `Config_types.id`. |
| `Cables`          | `id`, `label`, `radio`, `resistance`, `description`      | Radius in m, resistance in Ω/km. |
| `Config_types`    | `id`, `name`, `description`, `Geometry`                  | `Geometry` is a Python-literal list of `(cable_id, height_m, x_pos_m)`, for example `"[('ACSR_2/0',10,0), ('ACSR_2/0',10,2)]"`. |
| `Transformers`    | `id`, `label`, `from_node`, `phases`, `trf_type`         | `from_node` is a node label. `trf_type` is a `Trftype.id`. |
| `Trftype`         | `id`, `CHV`, `CLV`, `CHL`, `ground`                      | Capacitances in F, grounding resistance in Ω. |
| `Surge_Arresters` | `id`, `label`, `node`, `phases`, `file`                  | `file` is a `.pch` file name inside `surges/`. |

### Phase masks
Phases are given as integer masks built from 0/1 digits. **The two element types read
the digits in opposite orders**:

| Mask  | Transformers (units = A, tens = B, hundreds = C) | Surge arresters (hundreds = A, tens = B, units = C) |
|-------|--------------------------------------------------|-----------------------------------------------------|
| `1`   | A                                                | C                                                   |
| `11`  | A, B                                             | B, C                                                |
| `101` | A, C                                             | A, C                                                |
| `111` | A, B, C                                          | A, B, C                                             |

---

## Generated files

Every file is written under a directory named after the network (`<name>/`):

| File                                  | Produced by                     | Content |
|---------------------------------------|---------------------------------|---------|
| `<name>/<name>.atp`                   | `MakeAtpFile`                   | ATP case (branches, YALUK MODELS or direct-strike source, outputs) |
| `<name>/lcc/lcc_###.dat`              | `MakeLccFile`                   | JMarti LINE CONSTANTS setup per line |
| `<name>/lcc/lcc_###.dbm`              | `MakeLccFile`                   | DATA BASE MODULE file used to build the `.lib` |
| `<name>/lcc/lcc_###.pch`, `.lib`      | `MakeLccFile(run_solver=True)`  | Solver-generated punch file and line library |
| `<name>/CaseFiles/linea_###.txt`      | `MakeLineFiles`                 | YALUK line geometry: radius, end points, heights, resistances, positions |
| `<name>/CaseFiles/corr_#####.txt`     | `Lightning.MakeLightningFile`   | Heidler current parameters and strike location |
| `<name>/CaseFiles/miscelaneo.txt`     | `Project_lib.write_misc_file`   | Channel, soil and FDTD settings |
| `<name>/yaluk.ini`, `yaluk_status.ini`| `Project_lib.write_yaluk_init_file` | YALUK case configuration and output flags |

Buffer variants: `MakeATPBuffer()`, `MakeLineFiles(return_buffer=True)`,
`MakeLccFile(return_buffer=True)`, `Lightning.MakeLightningBuffer()`,
`Lightning_stat.Create_csvBuffer()`, and `buffer=True` on the `Project_lib` writers.

---

## Lightning modelling

### Monte Carlo defaults (`Lightning_stat`)

| Parameter                        | Default                                            |
|----------------------------------|----------------------------------------------------|
| Peak current, I ≤ 20 kA          | Lognormal, median 61 kA, σ = 1.33                  |
| Peak current, I > 20 kA          | Lognormal, median 33.3 kA, σ = 0.605               |
| Front time                       | Lognormal, median 3.83 µs, σ = 0.553, correlated with the peak current (ρ = 0.47) |
| Heidler `n`, decay time `tc`     | 4, 50 µs                                           |
| Strike area                      | Network bounding box + `dist` (1000 m) on each side, uniform |

All of these are attributes of the object and can be changed before calling
`GenStatCurrents()`.

### Direct vs. indirect strikes
- **Striking distance** to the conductor: `Rs = 10·I^0.65`, with I in kA. The striking
  distance to ground is `Rg = 0.9·Rs`.
- A stroke is **direct** when its distance to a line is less than or equal to the
  attractive radius computed from `Rs`, `Rg` and the line's highest conductor. The ATP
  case then models the current injection, and FDTD coupling is turned off.
- Otherwise the stroke is **indirect**. The library estimates the maximum induced voltage
  with a simplified Rusck expression (`≈ 1.2958·30·I·h/d`, in kV). Lines within
  `distance_threshold` are coupled to YALUK as illuminated lines. A threshold of 100 m or
  less means every line is coupled.

---

## Running the ATP solver

```python
from yaluk_network_lib.Network_lib import run_atp_file

run_atp_file("Example_Network/Example_Network.atp",
             solver_path=r"C:\EMTP\Solver\tp_yaluk.exe",  # optional
             keep_pl4=True)
```

The solver executable is found from, in order:
1. The `solver_path` argument.
2. The `SOLVER_PATH` environment variable.
3. `C:\EMTP\Solver\tp_yaluk.exe` on Windows.
4. `tp_yaluk.exe` (Windows) or `tpyaluk` (other systems) on `PATH`.

On Windows, `ATPDIR` and `GNUDIR` are set to the solver directory if they are not
already set. If the solver fails, the `RuntimeError` message includes the command,
stdout, stderr and the end of the `.lis` file.

---

## Plotting

```python
import matplotlib.pyplot as plt
from yaluk_network_lib.plot_lib import plot_lines, plot_nodes, plot_lightnings

net.create_dataframes()
fig, ax = plt.subplots(figsize=(10, 8))
plot_lines(net.df_lines, coord_type="car", ax=ax)
plot_nodes(net.df_nodes, coord_type="car", ax=ax)
plot_lightnings(stats.lightnings_df, coord_type="car", mode="categorical", ax=ax)
plt.show()
```

Use `coord_type="geo"` to plot in longitude/latitude.

---

## Units and conventions

| Quantity                    | Unit |
|-----------------------------|------|
| Coordinates, heights, radii | m    |
| Line length (LCC cards)     | km, converted internally |
| Conductor resistance        | Ω/km |
| Transformer capacitances    | F (input), written to ATP in µF |
| Lightning current           | A    |
| Times                       | s    |
| Rusck voltage               | kV   |
| Soil resistivity (LCC)      | Ω·m (default 100) |

- Network origin: the default reference point is lat 6.1924, lon −75.3979. When built
  with `network_setting()`, the origin is set from the node table. Lightning coordinates
  are relative to this origin.
- ATP node names: `N####P` for network nodes, `L####P`/`R####P` for the left and right
  ends of FDTD lines, and `T####` for transformers. `####` is the zero-padded index and
  `P` is the phase letter.

---

## Testing

```bash
# from the repository root (conftest.py adds the parent directory to sys.path)
pytest -q
```

---

## License

GNU General Public License v3.0. See [Network_lib/LICENSE](Network_lib/LICENSE).
