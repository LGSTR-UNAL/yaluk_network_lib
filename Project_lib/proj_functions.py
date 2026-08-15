from io import BytesIO
from pathlib import Path
from yaluk_network_lib.Lightning_lib.LightningChannel import LightningChannel
from yaluk_network_lib.Lightning_lib.Soil import Soil
from yaluk_network_lib.Network_lib.Network import Network
import yaluk_network_lib.Project_lib as yp


def write_misc_file(pr_settings, network, buffer=False):
    case_folder = Path(network.name) / "CaseFiles"
    case_folder.mkdir(parents=True, exist_ok=True)
    misc_file = case_folder / "miscelaneo.txt"

    if buffer:
        misc_file = BytesIO()
        misc_file.write(
            f"{pr_settings.Channel_settings.Velocity:0.00E} % Velocidad descarga retorno\n".encode()
        )
        misc_file.write(
            f"{pr_settings.Channel_settings.Atenuation_const:0.00E} % Atenuacion\n".encode()
        )
        misc_file.write(
            f"{pr_settings.Channel_settings.Heigth:0.00E} % Altura nube\n".encode()
        )
        misc_file.write(f"20E-6 % Tiempo maximo\n".encode())
        misc_file.write(f"40 % Número de puntos\n".encode())
        misc_file.write(
            f"{int(not pr_settings.Soil_settings.Perfectsoil)} % Conductividad activa\n".encode()
        )
        misc_file.write(
            f"{pr_settings.Soil_settings.Conductivity:0.00E} % Conductividad del terreno o(s / m)\n".encode()
        )
        misc_file.write(
            f"{pr_settings.Soil_settings.Permitivity:0.00E} % Permitividad del terreno e [p.u]\n".encode()
        )
        misc_file.write(
            f"{pr_settings.Sim_settings.Dx:g} % Espaciamiento en distancia dx(s / m)\n".encode()
        )
        misc_file.write(
            f"{int(pr_settings.Sim_settings.Typewaveform)} % Onda triangular o(s / m)\n".encode()
        )
        misc_file.write(
            f"{pr_settings.Sim_settings.MaxDistCamp} % !Maximum distance for calculating EM Fields [m]\n".encode()
        )
        misc_file.seek(0)
        return misc_file

    with open(misc_file, "w") as file:
        file.write(
            f"{pr_settings.Channel_settings.Velocity:0.00E} % Velocidad descarga retorno\n"
        )
        file.write(
            f"{pr_settings.Channel_settings.Atenuation_const:0.00E} % Atenuacion\n"
        )
        file.write(f"{pr_settings.Channel_settings.Heigth:0.00E} % Altura nube\n")
        file.write(f"20E-6 % Tiempo maximo\n")
        file.write(f"40 % Número de puntos\n")
        file.write(
            f"{int(not pr_settings.Soil_settings.Perfectsoil)} % Conductividad activa\n"
        )
        file.write(
            f"{pr_settings.Soil_settings.Conductivity:0.00E} % Conductividad del terreno o(s / m)\n"
        )
        file.write(
            f"{pr_settings.Soil_settings.Permitivity:0.00E} % Permitividad del terreno e [p.u]\n"
        )
        file.write(
            f"{pr_settings.Sim_settings.Dx:0.00E} % Espaciamiento en distancia dx(s / m)\n"
        )
        file.write(
            f"{int(pr_settings.Sim_settings.Typewaveform)} % Onda triangular o(s / m)\n"
        )
        file.write(
            f"{pr_settings.Sim_settings.MaxDistCamp} % !Maximum distance for calculating EM Fields [m]\n"
        )


def write_yaluk_init_file(
    pr_settings, network, buffer=False
) -> tuple[BytesIO, BytesIO] | None:

    fname = "yaluk.ini"
    yaluk_ini = Path(network.name) / fname
    # yaluk_ini = os.path.join(self.GenSettings.path, "yaluk.ini")

    if buffer:
        yaluk_ini = BytesIO()
        yaluk_ini.write(b"CaseFiles\n")
        yaluk_ini.write(b"1\n")
        yaluk_ini.write(f"{len(network.Lines)}\n".encode())
        max_cond = max(n.Num_conductors for n in network.Nodes)
        yaluk_ini.write(f"{max_cond}\n".encode())
        yaluk_ini.seek(0)

        status_buffer = BytesIO()
        status_buffer.write(f".{pr_settings.Sim_settings.Print_field}.\n".encode())
        status_buffer.write(f".{pr_settings.Sim_settings.Print_field_info}.\n".encode())
        status_buffer.write(f".{pr_settings.Sim_settings.Read_field}.\n".encode())
        status_buffer.write(f".{pr_settings.Sim_settings.Status_profile}.\n".encode())
        status_buffer.seek(0)
        return yaluk_ini, status_buffer
    else:
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


def create_project_files(
    pr_settings, network, stroke, solver_cwd, solver_path, buffer=False
):
    misc_file = write_misc_file(pr_settings, network, buffer=buffer)
    yaluk_ini, status_buffer = write_yaluk_init_file(
        pr_settings, network, buffer=buffer
    )
    stroke.MakeLightningFile(1, Path(network.name) / "CaseFiles")
    network.MakeAtpFile(
        stroke=stroke, distance_threshold=pr_settings.Sim_settings.MaxDistCamp
    )
    network.MakeLccFile(
        run_solver=True,
        solver_path=solver_path,
        solver_cwd=solver_cwd,
    )
    network.MakeLineFiles(return_buffer=False)
    return yaluk_ini, status_buffer, misc_file


def setup_settings(
    SimulationSettins_df, Channel_settings_df, Soil_settings_df, Atp_settings_df
):
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
