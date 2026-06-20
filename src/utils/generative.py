import os
from typing import Literal

from ui.tui import print_log
from utils.logger import get_logger

log = get_logger("generative")

type AIProvider = Literal["ollama", "gemini"]


def is_generative_ai_available() -> bool:
  provider = os.getenv("AI_PROVIDER", "gemini").lower()
  if provider == "ollama":
    if not os.getenv("OLLAMA_BASE_URL"):
      print_log("OLLAMA_BASE_URL not found in environment variables.")
      print_log("AI features will be disabled. Set it in your .env file to enable Ollama Cloud.")
      return False
    return True

  if not os.getenv("GEMINI_API_KEY"):
    print_log("GEMINI_API_KEY not found in environment variables.")
    print_log("AI features will be disabled. Set AI_PROVIDER=ollama or GEMINI_API_KEY in your .env file.")
    return False

  return True


def generate_content(prompt: str) -> str:
  provider = os.getenv("AI_PROVIDER", "gemini").lower()
  print(f"Calling {provider} API...")
  try:
    if provider == "ollama":
      return _generate_via_ollama(prompt)
    return _generate_via_gemini(prompt)
  except Exception as e:
    print_log(f"An error occurred during content generation: {e}", "ERROR")
    log.error("Content generation failed (%s): %s", provider, e, exc_info=True)
    return "Gagal menghasilkan konten dari AI."


def _generate_via_ollama(prompt: str) -> str:
  import httpx

  base_url = os.getenv("OLLAMA_BASE_URL", "").rstrip("/")
  api_key = os.getenv("OLLAMA_API_KEY")
  model = os.getenv("OLLAMA_MODEL", "qwen2.5")

  # Ollama Cloud exposes both the native /api/chat and the OpenAI-compatible
  # /v1/chat/completions endpoints. Use the OpenAI-compatible one for stability.
  url = f"{base_url}/v1/chat/completions"
  headers = {"Content-Type": "application/json"}
  if api_key:
    headers["Authorization"] = f"Bearer {api_key}"

  payload = {
    "model": model,
    "messages": [{"role": "user", "content": prompt}],
    "stream": False,
    "temperature": float(os.getenv("OLLAMA_TEMPERATURE", "0.7")),
  }

  with httpx.Client(timeout=60.0) as client:
    resp = client.post(url, json=payload, headers=headers)
    resp.raise_for_status()
    data = resp.json()

  choices = data.get("choices", [])
  if choices:
    content = choices[0].get("message", {}).get("content", "")
  else:
    content = data.get("message", {}).get("content", "")

  return (content or "").strip()


def _generate_via_gemini(prompt: str) -> str:
  from google import genai

  client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
  model = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
  response = client.models.generate_content(model=model, contents=prompt)
  return (response.text or "").strip()


def generate_description_prompt(program_title: str, activity_title: str, additional_context: str | None = None) -> str:
  return (
    f"Anda adalah seorang mahasiswa KKN UGM yang sedang mengisi logbook SIMASTER.\n"
    f"Buatkan 'Deskripsi Kegiatan' yang baik dan profesional untuk sebuah sub-kegiatan dalam logbook KKN.\n\n"
    f"**Informasi Konteks:**\n"
    f"- **Judul Program Kerja (Proker) Utama:** {program_title}\n"
    f"- **Judul Kegiatan Harian / Sub-Kegiatan:** {activity_title}\n\n"
    f"**Instruksi:**\n"
    f"1. Tulis deskripsi dalam Bahasa Indonesia yang formal dan jelas.\n"
    f"2. Deskripsi harus menjelaskan secara singkat apa yang dilakukan dalam kegiatan '{activity_title}' sebagai bagian dari program kerja '{program_title}'.\n"
    f"3. Jelaskan tujuan singkat dari kegiatan ini dan relevansinya terhadap proker utama.\n"
    f"4. Buat deskripsi minimal 300 karakter dan isian meliputi keterlibatan warga, tantangan yang dihadapi, bantuan dari pemerintah desa, kesesuaian dengan program desa"
    ", metodologi pendekatan yang dikerjakan dan tanggapan masyarakat. Jangan terlalu panjang. Jangan gunakan formatting, hanya response dengan deskripsi kegiatan.\n\n"
    f"**Contoh Output:**\n"
    f"Kegiatan ini merupakan bagian dari pelaksanaan program kerja '{program_title}'. "
    f"Fokus dari kegiatan ini adalah untuk [jelaskan tujuan singkat kegiatan]. "
    f"Hal ini dilakukan untuk mendukung pencapaian tujuan utama program kerja dalam [sebutkan relevansi dengan proker]."
    f"{f'**Konteks:**\n{additional_context}' if additional_context else ''}"
  )


def generate_result_prompt(proker_title: str, kegiatan_title: str, description: str) -> str:
  return (
    f"Anda adalah seorang mahasiswa KKN UGM yang sedang mengisi logbook SIMASTER.\n"
    f"Buatkan 'Hasil Kegiatan' yang baik dan positif untuk sebuah sub-kegiatan dalam logbook KKN.\n\n"
    f"**Informasi Konteks:**\n"
    f"- **Judul Program Kerja (Proker) Utama:** {proker_title}\n"
    f"- **Judul Kegiatan Harian / Sub-Kegiatan:** {kegiatan_title}\n"
    f"- **Deskripsi Kegiatan yang sudah dibuat:** {description}\n\n"
    f"**Instruksi:**\n"
    f"1. Tulis hasil kegiatan dalam Bahasa Indonesia yang formal.\n"
    f"2. Tuliskan bahwa kegiatan telah dilaksanakan dengan baik dan lancar.\n"
    f"3. Sebutkan output atau hasil positif yang singkat dan jelas dari kegiatan tersebut.\n"
    f"4. Buat hasil kegiatan dalam 1-2 kalimat saja. Jangan terlalu panjang (kurang dari 255 karakter). Jangan gunakan formatting, hanya response dengan hasil kegiatan saja\n\n"
    f"**Contoh Output:**\n"
    f"Kegiatan ini telah berhasil dilaksanakan sesuai dengan rencana dan berjalan dengan lancar. "
    f"Hasil yang dicapai adalah [sebutkan hasil positif singkat], memberikan kontribusi positif terhadap program kerja."
  )


def generate_report_narrative_prompt(summary_data: str) -> str:
  return (
    "Anda adalah seorang mahasiswa KKN UGM yang membuat laporan mingguan.\n"
    "Berdasarkan data kehadiran dan kegiatan KKN berikut, buatlah narasi ringkas "
    "(maksimal 3 paragraf) dalam Bahasa Indonesia yang formal.\n\n"
    "Narasi harus mencakup: ringkasan kehadiran, kegiatan utama yang dilakukan, "
    "dan rencana singkat untuk periode berikutnya. Jangan gunakan formatting markdown, "
    "hanya teks biasa.\n\n"
    f"**Data Kehadiran & Kegiatan:**\n{summary_data}"
  )
