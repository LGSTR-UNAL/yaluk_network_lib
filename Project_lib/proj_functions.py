from pathlib import Path
from Lightning_lib.LightningChannel import LightningChannel
from Lightning_lib.Soil import Soil
from Network_lib.Network import Network
import Project_lib as yp

def write_misc_file(pr_settings,network):
    case_folder = Path(network.name) / "CaseFiles"
    case_folder.mkdir(parents=True, exist_ok=True)
    misc_file = case_folder/ "miscelaneo.txt"
			
    with open(misc_file, "w") as file:
        file.write(f"{pr_settings.Channel_settings.Velocity:0.00E} % Velocidad descarga retorno\n")
        file.write(f"{pr_settings.Channel_settings.Atenuation_const:0.00E} % Atenuacion\n")
        file.write(f"{pr_settings.Channel_settings.Heigth:0.00E} % Altura nube\n")
        file.write(f"3E-6 % Tiempo maximo\n")
        file.write(f"30 % Número de puntos\n")
        file.write(
            f"{int(not pr_settings.Soil_settings.perfect_soil)} % Conductividad activa\n"
        )
        file.write(f"{pr_settings.Sim_settings.Conductivity:0.00E}\n")
        file.write(f"{pr_settings.Sim_settings.Permitivity:0.00E}\n")
        file.write(f"{pr_settings.Sim_settings.Dx:0.00E}\n")
        file.write(f"{int(pr_settings.Sim_settings.Typewaveform)}\n")
        file.write(f"{pr_settings.Sim_settings.MaxDistCamp}\n")
def write_yaluk_init_file(pr_settings,network):
    
    fname="yaluk.ini"
    yaluk_ini  = Path(network.name) / fname
    # yaluk_ini = os.path.join(self.GenSettings.path, "yaluk.ini")

    with open(yaluk_ini, "w") as file:
        file.write("CaseFiles\n")
        file.write("1\n")
        file.write(f"{len(network.Lines)}\n")
        max_cond = max(n.Num_conductors for n in network.Nodes)
        file.write(f"{max_cond}\n")

    # status
    status_file = Path(network.name) / "yaluk_status.ini"

    with open(status_file, "w") as file:
        file.write(f".{pr_settings.Sim_settings.Print_field}.\n")
        file.write(f".{pr_settings.Sim_settings.Print_field_info}.\n")
        file.write(f".{pr_settings.Sim_settings.Read_field}.\n")
        file.write(f".{pr_settings.Sim_settings.Status_profile}.\n")

def create_project_files(pr_settings,network,stroke):   
    write_misc_file(pr_settings,network)
    write_yaluk_init_file(pr_settings,network)
    stroke.MakeLightningFile(1, Path(network.name) / "CaseFiles")
    network.MakeAtpFile(stroke=stroke, distance_threshold=pr_settings.Sim_settings.MaxDistCamp)
    network.MakeLccFile(run_solver=True,
                        solver_path=r"C:\EMTP\Solver\tp_yaluk.exe",
                        solver_cwd=r"C:\EMTP\Solver",)
    network.MakeLineFiles(return_buffer=False)
 

def setup_settings(SimulationSettins_df, 
                  Channel_settings_df, 
                  Soil_settings_df, 
                  Atp_settings_df):
    project = yp.ProjectSettings()

    settings = yp.SimulationSettings()
    for key, value in SimulationSettins_df.iloc[0].to_dict().items():
        setattr(settings, key, value)
    project.Sim_settings = settings

    settings = LightningChannel()
    for key, value in Channel_settings_df.iloc[0].to_dict().items():
        setattr(settings, key, value)
    project.Channel_settings = settings

    settings = Soil()
    for key, value in Soil_settings_df.iloc[0].to_dict().items():
        setattr(settings, key, value)
    project.Soil_settings = settings

    settings = Network.AtpSettings()
    for key, value in Atp_settings_df.iloc[0].to_dict().items():
        setattr(settings, key, value)
    project.Atp_settings = settings

    print("Project settings setup completed.")

    return project
