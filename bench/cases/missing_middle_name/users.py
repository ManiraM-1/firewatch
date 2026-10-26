def full_name(user):
    parts = [user["first"], user.get("middle"), user["last"]]
    return " ".join(parts)


def initials(user):
    return "".join(part[0].upper() for part in full_name(user).split())


def display_name(user):
    nickname = user.get("nickname")
    if nickname:
        return f"{nickname} ({full_name(user)})"
    return full_name(user)
