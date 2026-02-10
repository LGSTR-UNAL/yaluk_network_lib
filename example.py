import Network_lib as nl
import pandas as pd

from Network_lib.Node import PhaseName
class Trf_parameters():
        def __init__(self,A,B,C,D):
            self.CapHV=A
            self.CapHL=B
            self.CapLV=C
            self.Ground=D

def data_setting():
    #Definition Nodes
    #id of the node must be integer or string of maximum 4 characters, preferably integer, label is the name of the node, x and y are the coordinates in meters from the initial location defined in the network_setting function, if ctype is "rel" the coordinates are relative to the initial location, if ctype is "abs" the coordinates are absolute from the initial location
    Nodes = pd.DataFrame(columns=['id', 'label','y','x'])
    Nodes.loc[0] = [1, 'N1', 125300, 103000]
    Nodes.loc[1] = [2, 'N2', 125350, 103050]
    Nodes.loc[2] = [3, 'N3', 125400, 103100]
    Nodes.loc[3] = [4, 'N4', 125450, 103150]

    #Definition Lines
    "from_node to to_node must be the id of the nodes defined in the Nodes dataframe, configuration_type must be one of the configurations defined in the network_setting function"
    Lines=pd.DataFrame(columns=['id', 'label', 'from_node', 'to_node','configuration_type'])
    Lines.loc[0] = [1, 'L1', 1, 2,'Config_A']
    Lines.loc[1] = [2, 'L2', 2, 3,'Config_A']
    Lines.loc[2] = [3, 'L3', 3, 4,'Config_B']

    #Definition high frequency transformer types
    
    Tr1= Trf_parameters(340e-12, 744e-12, 215e-12, 10)
    Tr2= Trf_parameters(440e-12, 644e-12, 115e-12, 20)

    #Transformers connections
    Transformers=pd.DataFrame(columns=['id', 'label', 'from_node', 'phases','trf_type'])
    Transformers.loc[0] = [1, 'T1', 2, 111,'Tr1']
    Transformers.loc[1] = [2, 'T2', 1, 11,'Tr2']
    Transformers.loc[2] = [3, 'T3', 3, 101,'Tr1']
    #Transformers Types

    Trftype=pd.DataFrame(columns=['id', 'CHV', 'CLV', 'CHL', 'ground'])
    Trftype.loc[0] = ['Tr1', 340e-12, 215e-12, 744e-12,10.0]
    Trftype.loc[1] = ['Tr2', 440e-12, 115e-12, 644e-12,20.0]


    #surge arresters
    Surge_Arresters=pd.DataFrame(columns=['id', 'label', 'node', 'phases','type'])
    Surge_Arresters.loc[0] = [1, 'SA1', 2,11,'Type_A']
    Surge_Arresters.loc[1] = [2, 'SA2', 3,1,'Type_B']
    return Nodes, Lines, Transformers, Surge_Arresters, Trftype

def network_setting(Nodes: pd.DataFrame, Lines:pd.DataFrame, Transformers:pd.DataFrame, Surge_Arresters:pd.DataFrame,Trftype:pd.DataFrame):
    # Create a new network
    len_nodes= len(Nodes)
    len_lines= len(Lines)
    len_transformers= len(Transformers)
    len_surge_arresters= len(Surge_Arresters)
    if len_nodes==0:
        raise ValueError("No nodes defined in the network.")
    elif len_lines==0:
        raise ValueError("No lines defined in the network.")
    print(f"Creating network with {len_nodes} nodes, {len_lines} lines, {len_transformers} transformers, and {len_surge_arresters} surge arresters.")
    # Initial location for coordinate conversion
    #Init_lat_lon= nl.PointLatLng(Nodes.loc[0,'x'], Nodes.loc[0,'y'])
    initxy=nl.PointXY(Nodes.loc[0,'x'], Nodes.loc[0,'y'])
 
    net = nl.Network('uid_01','Example_Network')
    net.InitXY=initxy
    
    Conductor_1 = nl.Conductor()
    Conductor_1.Radio = .005
    Conductor_1.Resistance = 1
    Conductor_1.Name = "Conductor ACSR"
    Conductor_1.Description = "Conductor Calibre 2/0 - catálogo CENTELSA"

    # Dfining Configurations, it culd be severalconfigurations with different number of conductors and geometries, each line must be assigned to one of the configurations
    Config1 = nl.Configuration_Type()
    Config1.id = "LAR1"
    Config1.Name = "Mono LAR1"
    Config1.Description = "Linea un solo conductor"
    Config1.Add_conductor(Conductor_1, 10, 0)
    Config1.Add_conductor(Conductor_1, 10, 2)
    Config1.gen_parameters()

    nl.Transformer
    
    for n in Nodes.itertuples():
       net.AddNode(n.x, n.y,Nodeidx=n.id,ctype="abs")  #You can use also ctype="rel" if you want to add nodes using coordinates relative to the initial location
    # Add lines
    for l in Lines.itertuples():
        from_node = net.Nodes.GetByIdx(l.from_node)
        to_node = net.Nodes.GetByIdx(l.to_node)
        net.AddLine(from_node, to_node, Config1)
    for li in net.Lines:
        li.isFDTD=True
    net.MakeLccFile()
    # Add transformers
    for t in Transformers.itertuples():
        node_trf=t.from_node
        trf_types = Trftype.loc[Trftype['id'] == t.trf_type]
        trf_type = trf_types.iloc[0] if not trf_types.empty else None
        net.AddTransf(label=t.label,CHV=float(trf_type.CHV), CLV=float(trf_type.CLV), CHL=float(trf_type.CHL), ground=float(trf_type.ground), NHV=node_trf,  phases=t.phases)
        
    return net
 

    
if __name__ == "__main__":
    print("Starting network creation...")
    Nodes,Lines,Transformers,Surge_Arresters,Trftype = data_setting()
    print("Data setting completed.")
    print("Creating network...")
    net=network_setting(Nodes,Lines,Transformers,Surge_Arresters,Trftype)
    print("Network created successfully.")
    print("Generating ATP file...")
    
    net.MakeAtpFile()
    print("ATP file generated.")
    print("Process completed.")
    