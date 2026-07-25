# Función para crear la red a partir de los datos definidos en los DataFrames
from yaluk_network_lib import Network_lib as nl
import pandas as pd
#Función para crear la red a partir de datos definidos en archivos csv
from os import PathLike
from pathlib import Path


def build_conductors_db(Cables: pd.DataFrame) -> dict:
    """Build a dict of Conductor objects keyed by Cables['id']."""
    conductors_db = {}
    for _, row in Cables.iterrows():
        conductor = nl.Conductor()
        conductor.Radio = row['radio']
        conductor.Resistance = row['resistance']
        conductor.Name = row['label']
        conductor.Description = row['description']
        conductors_db[row['id']] = conductor
    return conductors_db


def _read_network_csv(csv_file: str | PathLike[str], label: str) -> pd.DataFrame:
    """Read a network CSV from a normalized and validated path."""
    if not isinstance(csv_file, (str, PathLike)):
        raise TypeError(f"{label} must be a path-like value, got {type(csv_file).__name__}.")

    if isinstance(csv_file, str):
        csv_file = csv_file.strip().strip('"').strip("'")

    path = Path(csv_file).expanduser()

    if path.suffix.lower() != ".csv":
        raise ValueError(f"{label} must be a .csv file: {path}")

    try:
        path = path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"{label} CSV file does not exist: {path}") from exc

    if not path.is_file():
        raise FileNotFoundError(f"{label} CSV path is not a file: {path}")

    return pd.read_csv(path)


def network_setting_csv(
                    Nodes_csv: str | PathLike[str],
                    Lines_csv: str | PathLike[str],
                    Transformers_csv: str | PathLike[str],
                    Surge_Arresters_csv: str | PathLike[str],
                    Trftype_csv: str | PathLike[str],
                    Cables_csv: str | PathLike[str],
                    Config_types_csv: str | PathLike[str],
                    name_net: str = None) -> nl.Network:
    Nodes = _read_network_csv(Nodes_csv, "Nodes")
    Lines = _read_network_csv(Lines_csv, "Lines")
    Transformers = _read_network_csv(Transformers_csv, "Transformers")
    Surge_Arresters = _read_network_csv(Surge_Arresters_csv, "Surge_Arresters")
    Trftype = _read_network_csv(Trftype_csv, "Trftype")
    Cables = _read_network_csv(Cables_csv, "Cables")
    Config_types = _read_network_csv(Config_types_csv, "Config_types")

    return network_setting(Nodes, Lines, Transformers, Surge_Arresters, Trftype, Cables, Config_types, name_net)


def network_setting(
                    Nodes: pd.DataFrame, 
                    Lines:pd.DataFrame, 
                    Transformers:pd.DataFrame, 
                    Surge_Arresters:pd.DataFrame,
                    Trftype:pd.DataFrame,
                    Cables:pd.DataFrame,
                    Config_types:pd.DataFrame, 
                    name_net:str=None)-> nl.Network:
    
    #setting the length of the dataframes for later use
    len_nodes= len(Nodes)
    len_lines= len(Lines)
    len_transformers= len(Transformers)
    len_surge_arresters= len(Surge_Arresters)
    len_cables= len(Cables)
    len_line_config= len(Config_types)

    if name_net==None:
        name_net="Network_1"
        print("No name provided for the network, using default name 'Network_1'")

    # Create a new network
    if len_nodes==0:
        raise ValueError("No nodes defined in the network.")
    elif len_lines==0:
        raise ValueError("No lines defined in the network.")
    print(f'''Creating network with {len_nodes} nodes, {len_lines} lines, {len_transformers} transformers, 
          {len_surge_arresters} surge arresters, {len_cables} cables, and {len_line_config} line configurations.''')
    
    # Initial location for coordinate conversion
    #Init_lat_lon= nl.PointLatLng(Nodes.loc[0,'x'], Nodes.loc[0,'y'])
    initxy=nl.PointXY(Nodes.loc[1,'x'], Nodes.loc[1,'y'])

    #Creating network object
    net = nl.Network('uid_01',name_net)
    net.InitXY=initxy
    
    # Creating conductors database
    Conductors_db = build_conductors_db(Cables)

    #creating line configurations database
    import ast
    Configurations_db={}
    for i, row in Config_types.iterrows():
        config = nl.Configuration_Type()
        config.id = row['id']
        config.Name = row['name']
        config.Description = row['description']
        geometry = ast.literal_eval(row['Geometry'])
        for conductor_info in geometry:
            if len(conductor_info) != 3:
                raise ValueError(f"Invalid geometry entry: {conductor_info}")
            conductor_id, x, y = conductor_info
            conductor = Conductors_db[conductor_id]
            config.Add_conductor(conductor, x, y)
        config.gen_parameters()
        Configurations_db[row['id']] = config

    for n in Nodes.itertuples():
       net.AddNode(n.x, n.y,Nodeidx=n.id,ctype="abs", label=n.label)  #You can use also ctype="rel" if you want to add nodes using coordinates relative to the initial location
    
    # Add lines
    for l in Lines.itertuples():
        from_node = net.Nodes.GetByName(l.from_node)
        to_node = net.Nodes.GetByName(l.to_node)
        config_type=Configurations_db[l.configuration_type]
        net.AddLine(from_node, to_node, config_type)
    for li in net.Lines:
        li.isFDTD=True

    # Add transformers

    for t in Transformers.itertuples():
        node_trf=t.from_node
        trf_types = Trftype.loc[Trftype['id'] == t.trf_type]
        trf_type = trf_types.iloc[0] if not trf_types.empty else None
        net.AddTransf(label=t.label,CHV=float(trf_type.CHV), CLV=float(trf_type.CLV), CHL=float(trf_type.CHL), ground=float(trf_type.ground), NHV=node_trf,  phases=t.phases)
    
    ruta = Path('surges')
    for sa in Surge_Arresters.itertuples():
        node_sa=net.Nodes.GetByName(sa.node)
        filename_short=str(ruta / sa.file)
        #filename_short=get_short_path(filename_short)
        net.AddSurgeArrester(ni=node_sa,pch_file=filename_short, Phase_connect=sa.phases)
    return net
