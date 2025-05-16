WARN_EMOJI = "<:warning:1350239604925530192>"
SUCCESS_EMOJI = "<:vericheck:1301647869505179678>"

def warn(user, message: str):
    return f"{WARN_EMOJI} {user.mention}: {message}"

def success(user, message: str):
    return f"{SUCCESS_EMOJI} {user.mention}: {message}"
