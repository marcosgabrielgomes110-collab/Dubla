# Dubla_Input — entradas de vídeo

Tudo que transforma um vídeo (remoto ou local) no formato que o resto do Dubla consome:
para cada vídeo é criada a pasta `Data/temp/<id>/` com

| Arquivo | Conteúdo |
| --- | --- |
| `<id>.mp4` | vídeo **sem áudio** (a faixa de áudio é removida no fim do pipeline) |
| `<id>.wav` | áudio separado, mono, 16 kHz, PCM s16le |
| `<id>.json` | metadados + `video_path` e `audio_path` |

Os caminhos vêm de `configs.json` (`temp_path`, `output_path`), resolvidos a partir da raiz do projeto.

## Resumo

| Arquivo | Classe | Entrada | Retorno do `run()` |
| --- | --- | --- | --- |
| `Link_Movie.py` | `GetLinkMovie` | URL do YouTube (`str`) | `Path` do `<id>.json` — ou `None` em erro |
| `Local_Movie.py` | `GetLocalMovie` | caminho de um vídeo local (`str` ou `Path`) | `Path` do `<id>.json` — ou `None` em erro |

Uso:

```python
from src.Dubla_Input.Link_Movie import GetLinkMovie
from src.Dubla_Input.Local_Movie import GetLocalMovie

meta = GetLinkMovie("https://www.youtube.com/watch?v=x7X9w_GIm1s").run()
meta = GetLocalMovie("~/Videos/filme.mkv").run()
```

## `Link_Movie.py` — download do YouTube

- **Entrada:** URL. O `__init__` já consulta o yt-dlp só para obter o ID do vídeo (não baixa nada).
- **Fluxo:** `prepare()` → download na qualidade de `configs.json` (`quality_ytdlp`) → extrai `<id>.wav` → remove o áudio do `.mp4` → grava o JSON.
- **ID:** o próprio ID do YouTube (ex.: `x7X9w_GIm1s`).
- **Recuperação:** se o `.mp4` local já está mudo (run anterior), força o yt-dlp a baixar de novo, porque o áudio original não existe mais no disco.
- **Cache:** se vídeo + WAV + JSON já existem, `run()` retorna o JSON na hora, sem rede.

## `Local_Movie.py` — vídeo local

- **Entrada:** caminho de arquivo. `__init__` valida a existência (`FileNotFoundError` se não achar) e calcula o ID.
- **ID:** SHA-256 do conteúdo, 16 caracteres hex — o mesmo arquivo sempre cai na mesma pasta, mesmo se for renomeado.
- **Fluxo:** `prepare()` → valida que a origem tem áudio → copia o `.mp4` ou **converte** outros containers (`.mkv`, `.avi`, `.mov`, `.webm`; remux quando o codec cabe em mp4, senão reencode H.264/AAC) → extrai `<id>.wav` → remove o áudio do `.mp4` → grava o JSON.
- **Original:** nunca é apagado nem movido, apenas copiado.
- **Cache:** mesma regra do `Link_Movie.py`.

## JSON gerado

```json
{
    "id": "x7X9w_GIm1s",
    "title": "Python in 100 Seconds",
    "duration": 143,
    "uploader": "Fireship",
    "resolution": "1280x720",
    "ext": "mp4",
    "video_path": ".../Data/temp/x7X9w_GIm1s/x7X9w_GIm1s.mp4",
    "audio_path": ".../Data/temp/x7X9w_GIm1s/x7X9w_GIm1s.wav",
    "file_path": ".../Data/temp/x7X9w_GIm1s/x7X9w_GIm1s.mp4"
}
```

- `Local_Movie.py` inclui também `source_path` (arquivo original) e usa `uploader: null`.
- `file_path` é um alias antigo de `video_path`, mantido por compatibilidade.

## Pré-requisitos

`ffmpeg` e `ffprobe` no `PATH` (usados para converter, extrair o áudio, silenciar o vídeo e ler duração/resolução), além de `yt-dlp` para o `Link_Movie.py`.
