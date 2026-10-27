"""Entradas de vídeo: download do YouTube e arquivos locais.

Uso:
    from src.Dubla_Input import GetLinkMovie, GetLocalMovie

    meta = GetLinkMovie(url).run()
    meta = GetLocalMovie(path).run()
"""

from src.Dubla_Input.Link_Movie import GetLinkMovie
from src.Dubla_Input.Local_Movie import GetLocalMovie

__all__ = ["GetLinkMovie", "GetLocalMovie"]
