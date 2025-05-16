import time
from datetime import datetime
from typing import Union


def date(
    target: Union[datetime, float, int],
    clock: bool = True,
    ago: bool = False,
    only_ago: bool = False,
) -> str:
    """Converts a timestamp to a Discord timestamp format"""
    if isinstance(target, (int, float)):
        target = datetime.utcfromtimestamp(target)

    unix = int(time.mktime(target.timetuple()))
    timestamp = f"<t:{unix}:{'f' if clock else 'D'}>"
    if ago:
        timestamp += f" (<t:{unix}:R>)"
    if only_ago:
        timestamp = f"<t:{unix}:R>"
    return timestamp