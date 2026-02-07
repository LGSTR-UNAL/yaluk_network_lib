
from YalukProject import YalukProject
from Network_lib import Node, PointLatLng, Configuration_Type, Conductor


def main():
    project = YalukProject()

    # Example: build network
    n1 = project.Network.AddNode(PointLatLng(6.19, -75.39))
    n2 = project.Network.AddNode(100.0, 0.0)

    # Example lightning
    project.BuildLightning()

    # Save and export
    project.ProjectName = "example_case"
    project.SaveProject("./case/")
    project.Network.MakeAtpFile("./case/")

if __name__ == "__main__":
    main()
