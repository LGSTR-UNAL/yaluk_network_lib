# LCC cards for LCC file generation
def branch_card_lcc(num_conductors, max_len=80):
    prefix = "BRANCH  "
    lines = []
    current_line = prefix

    for k in range(1, num_conductors + 1):
        token = f"IN_{k:03d}OUT{k:03d}"
        if len(current_line) + len(token) > max_len:
            lines.append(current_line)
            current_line = prefix + token
        else:
            current_line += token
    current_line+="\n"
    lines.append(current_line)
    return "".join(lines)

def arg_card_lcc(num_conductors, max_len=80):
    prefix = "ARG,"
    lines = []
    current_line = prefix

    for k in range(1, num_conductors + 1):
        for token in (f"IN_{k:03d}", f"OUT{k:03d}"):
            # +1 for comma if needed
            addition = ("" if current_line.endswith(",") else ",") + token

            if len(current_line) + len(addition) > max_len:
                lines.append(current_line)
                current_line = token  # new line without prefix
            else:
                current_line += addition
    current_line+="\n"
    lines.append(current_line)
    return "\n".join(lines)
def conductor_card_lcc(idx, cp):
    """
    Fixed-format conductor card (METRIC section)
    """
    Rin=0
    Reff=cp.Conduct.Radio-Rin
    React=""
    return (
        f"{idx:>3d}"                    #Ph.no
        f"{Reff:>5.3f}"               #Rin/2
        f"{cp.Conduct.Resistance:>8.6f}"#Resis [Ohm]
        f"{4:>2}"               # opt:4 skin effect, 0 no skin effect
        f"{React:>8}"           # For Reactance use when no consider skin effect
        f"{cp.Conduct.Radio*2:>8.6f}"         #Diameter
        f"{cp.Relative_X_location:>8.2f}"#horiz
        f"{cp.Height:>8.2f}"    #Vtwer
        f"{cp.Height:>8.2f}"    #Vmid
    )
