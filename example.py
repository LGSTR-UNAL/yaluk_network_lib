import Network_lib as nl
import pandas as pd
class Trf_parameters():
        def __init__(self,A,B,C,D):
            self.CapHV=A
            self.CapHL=B
            self.CapLV=C
            self.Ground=D

def data_setting():
    #Definition Nodes
    Nodes = pd.DataFrame(columns=['id', 'label','lat','lon'])
    Nodes.loc[0] = [1, 'N1', 5.0522, -76.2437]
    Nodes.loc[1] = [2, 'N2', 5.0522, -76.2537]
    Nodes.loc[2] = [3, 'N3', 5.0572, -76.2637]
    Nodes.loc[3] = [4, 'N4', 5.0622, -76.2737]

    #Definition Lines
    Lines=pd.DataFrame(columns=['id', 'label', 'from_node', 'to_node','configuration_type'])
    Lines.loc[0] = [1, 'L1', 1, 2,'Config_A']
    Lines.loc[1] = [2, 'L2', 2, 3,'Config_A']
    Lines.loc[2] = [3, 'L3', 3, 4,'Config_B']

    #Definition high frequency transformer types
    
    Tr1= Trf_parameters(340e-12, 744e-12, 215e-12, 10)
    Tr2= Trf_parameters(440e-12, 644e-12, 115e-12, 20)

    #Transformers connections
    Transformers=pd.DataFrame(columns=['id', 'label', 'from_node', 'to_node','phases','trf_type'])
    Transformers.loc[0] = [1, 'T1', 2, 4,111,Tr1]
    Transformers.loc[1] = [2, 'T2', 1, 3,11,Tr2]
    Transformers.loc[2] = [3, 'T3', 1, 4,101,Tr1]

    #surge arresters
    Surge_Arresters=pd.DataFrame(columns=['id', 'label', 'node', 'phases','type'])
    Surge_Arresters.loc[0] = [1, 'SA1', 2,11,'Type_A']
    Surge_Arresters.loc[1] = [2, 'SA2', 3,1,'Type_B']
    return Nodes, Lines, Transformers, Surge_Arresters

def network_setting(Nodes: pd.DataFrame, Lines:pd.DataFrame, Transformers:pd.DataFrame, Surge_Arresters:pd.DataFrame):
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
    Init_lat_lon= nl.PointLatLng(Nodes.loc[0,'lat'], Nodes.loc[0,'lon'])
    net = nl.Network('uid_01','Example_Network')
    net.InitLatLong=Init_lat_lon

    Conductor_1 = nl.Conductor()
    Conductor_1.Radio = .005
    Conductor_1.Resistance = 1
    Conductor_1.Name = "Conductor ACSR"
    Conductor_1.Description = "Conductor Calibre 2/0 - catálogo CENTELSA"


    Config1 = nl.Configuration_Type()
    Config1.id = "LAR1"
    Config1.Name = "Mono LAR1"
    Config1.Description = "Linea un solo conductor"
    Config1.Add_conductor(Conductor_1, 10, 0)
    Config1.Add_conductor(Conductor_1, 10, 2)
    Config1.gen_parameters()
    
    for n in Nodes.itertuples():
        node = nl.Node(nl.PointLatLng(n.lat, n.lon))
        node.id = n.id
        node.Name = n.label
        node.XY_2_LatLng(Init_lat_lon)
        net.AddNode(n.lat, n.lon, n.id)
    # Add lines
    for l in Lines.itertuples():
        from_node = net.Nodes.GetByIdx(l.from_node)
        to_node = net.Nodes.GetByIdx(l.to_node)
        Config_1= nl.Configuration_Type()
        Config_1.Type='Config_A'
        # Here we would set the configuration type based on l.configuration_type
        net.AddLine(from_node, to_node, Config1)
    for li in net.Lines:
        li.isFDTD=True
    net.MakeLccFile()
    return net
    

    
if __name__ == "__main__":
    print("Starting network creation...")
    Nodes,Lines,Transformers,Surge_Arresters = data_setting()
    print("Data setting completed.")
    print("Creating network...")
    net=network_setting(Nodes,Lines,Transformers,Surge_Arresters)
    print("Network created successfully.")
    print("Generating ATP file...")
    
    net.MakeAtpFile()
    print("ATP file generated.")
    print("Process completed.")
    