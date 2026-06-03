# QLDA-AI-GHI-CUOC-HOP

[English](#english) | [Tiếng Việt](#tiếng-việt)

## English

AI Meeting Assistant helps teams record meetings, transcribe speech to text, identify speakers, translate between English and Vietnamese, summarize long transcripts, ask questions over meeting content with RAG, manage meetings, and track action items.

### Table of Contents

- [Overview](#overview)
- [Business Scope](#business-scope)
- [Main Features](#main-features)
- [System Architecture](#system-architecture)
- [Folder Structure](#folder-structure)
- [Tech Stack](#tech-stack)
- [Requirements](#requirements)
- [Environment Configuration](#environment-configuration)
- [Run With Docker](#run-with-docker)
- [Run Services Manually](#run-services-manually)
- [Database and Prisma](#database-and-prisma)
- [AI Server](#ai-server)
- [Audio Processing Flow](#audio-processing-flow)
- [Realtime Recording](#realtime-recording)
- [RAG Q&A With Chroma](#rag-qa-with-chroma)
- [Frontend](#frontend)
- [Backend API](#backend-api)
- [Testing](#testing)
- [Common Docker Commands](#common-docker-commands)
- [Git Push Guide](#git-push-guide)
- [Troubleshooting](#troubleshooting)
- [Security and Performance Notes](#security-and-performance-notes)

### Overview

The project contains three main parts:

1. `frontend`: a React/Vite user interface for dashboard, recording, audio upload, meeting list, meeting detail, and action items.
2. `backend`: a Node.js/Express REST API with Prisma ORM, PostgreSQL, Swagger, file upload, PDF/DOCX/JSON export, and a WebSocket recording bridge.
3. `app`: a FastAPI AI server for STT, speaker diarization, translation, summarization, LLM Q&A, and vector indexing.

In the current Docker setup, Docker runs only `frontend` and `backend`. PostgreSQL and the AI server run directly on the host machine so local GPU and local models can be used more reliably.

### Business Scope

The system manages the full lifecycle of meeting content: recording or uploading audio, converting it into a transcript, identifying speakers, summarizing the discussion, extracting action items, searching previous content, asking questions, and exporting meeting minutes.

The goal is to reduce manual note-taking work. Instead of asking participants to write meeting minutes during the call, the system receives audio, processes it with AI, stores structured content, and gives users tools to review, edit, confirm, manage, and reuse meeting information.

Main workflow:

```text
Create/select a meeting
  -> Record audio or upload an audio file
  -> Choose transcript-only or speaker-label mode
  -> AI converts audio into transcript
  -> Save transcript, speakers, and file metadata to the database
  -> User reviews and edits the content
  -> Generate summary, keywords, sentiment, and action items
  -> Ask questions over the meeting transcript with LLM + Chroma
  -> Manage action items after the meeting
  -> Export meeting minutes as PDF/DOCX/JSON
```

### Main Features

- Meeting management: create, update, soft-delete, search, filter, and view meeting details.
- Audio upload and STT: upload audio, stream transcript chunks, and save transcripts to PostgreSQL.
- Speaker diarization: detect speaker timelines and map transcript segments to speaker labels.
- Realtime recording: stream browser microphone chunks through WebSocket and show live transcript output.
- Translation: translate Vietnamese to English and English to Vietnamese with local models.
- Summary and Q&A: summarize transcripts and answer questions with LLM + Chroma retrieval.
- Action items: manage tasks in `Todo`, `In progress`, and `Done` columns.
- Dashboard: show meeting, transcript, summary, audio, sentiment, speaker, keyword, and action item statistics.
- Export: export meeting content as PDF, DOCX, or JSON with Unicode Vietnamese support.

### System Architecture

```text
Browser
  |
  | HTTP / WebSocket
  v
Frontend React/Vite :5173
  |
  | REST API
  v
Backend Node.js/Express :3001
  |
  | Prisma
  v
PostgreSQL :5432

Backend Node.js
  |
  | HTTP multipart / JSON
  v
AI Server FastAPI :8000
  |
  | Local models + Ollama + Chroma
  v
STT / Diarization / Translation / LLM / RAG
```

The backend acts as the API gateway for the frontend and stores business data in PostgreSQL. The AI server isolates heavy model processing from the Node.js backend.

### Folder Structure

```text
.
├── app/                       # FastAPI AI server
│   ├── main.py                # AI API entrypoint
│   ├── config.py              # Model, GPU, Ollama, and Chroma configuration
│   └── services/              # STT, diarization, pipeline, RAG, translation
├── backend/                   # Node.js Express backend
│   ├── prisma/                # Prisma schema, migrations, seed
│   ├── scripts/               # API smoke tests
│   └── src/                   # Config, controllers, routes, services, middleware
├── frontend/                  # React/Vite frontend
│   └── src/                   # Components, layouts, pages, routes, services, styles
├── data/                      # Runtime data, uploads, processed files, Chroma
├── uploads/                   # Runtime upload files
├── docker-compose.yml         # Docker frontend/backend setup
├── docker-compose.dev.yml     # Hot reload compose override
├── .env.example               # AI server environment example
├── .env.docker.example        # Docker environment example
├── Dockerfile.ai              # Reference AI Dockerfile
└── run.py                     # AI server launcher with pre-flight checks
```

### Tech Stack

Frontend:

- React 18
- Vite
- React Router
- Tailwind CSS
- Axios
- Browser WebSocket API

Backend:

- Node.js 22+
- Express.js
- PostgreSQL
- Prisma ORM
- JWT authentication and role-based authorization
- Zod validation
- Swagger/OpenAPI
- Multer upload
- Winston logger
- Helmet, CORS, rate limiting
- PDFKit, docx
- WebSocket `ws`

AI server:

- Python FastAPI
- PyTorch
- PhoWhisper / local STT model
- Local speaker diarization model
- Local VI -> EN and EN -> VI translation models
- Ollama `qwen2.5:7b` for LLM
- Ollama `nomic-embed-text` for embeddings
- Chroma vector DB
- FFmpeg

### Requirements

Required:

- Node.js `22+`
- npm
- Python `3.10+` or a version compatible with the current AI dependencies
- PostgreSQL
- Docker Desktop
- FFmpeg
- Ollama

Recommended for GPU AI processing:

- NVIDIA GPU
- CUDA runtime compatible with the installed PyTorch version
- At least 4 GB VRAM
- Low VRAM mode enabled:

```env
AI_LOW_VRAM_MODE=1
PRELOAD_MODELS=0
STT_DEVICE=cuda
DIARIZATION_DEVICE=cuda
STT_CHUNK_DURATION=15
STT_MAX_NEW_TOKENS=256
```

### Environment Configuration

AI server `.env`:

```powershell
copy .env.example .env
```

Important variables:

```env
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5:7b
OLLAMA_EMBED_MODEL=nomic-embed-text

STT_MODEL_DIR=C:\Users\ADMIN\PhoWhisper-medium
DIARIZATION_MODEL_DIR=.\diarization\speaker-diarization-community-1
TRANSLATION_VI_EN_DIR=C:\Users\ADMIN\opus-mt-vi-en
TRANSLATION_EN_VI_DIR=C:\Users\ADMIN\opus-mt-en-vi

AI_LOW_VRAM_MODE=1
PRELOAD_MODELS=0
STT_DEVICE=cuda
DIARIZATION_DEVICE=cuda
```

Docker environment:

```powershell
copy .env.docker.example .env.docker
```

Example:

```env
DOCKER_DATABASE_URL=postgresql://postgres:17122005@host.docker.internal:5432/ai_meeting_assistant?schema=public
DOCKER_AI_SERVICE_URL=http://host.docker.internal:8000

DATABASE_URL=postgresql://postgres:17122005@host.docker.internal:5432/ai_meeting_assistant?schema=public
AI_SERVICE_URL=http://host.docker.internal:8000
AUTH_DISABLED=true
```

Backend `.env` when running manually:

```powershell
cd backend
copy .env.example .env
```

Example:

```env
PORT=3001
DATABASE_URL=postgresql://postgres:17122005@localhost:5432/ai_meeting_assistant?schema=public
AI_SERVICE_URL=http://localhost:8000
FRONTEND_ORIGIN=http://localhost:5173
AUTH_DISABLED=true
```

### Run With Docker

Before starting Docker, run PostgreSQL and the AI server on the host machine.

Start the AI server:

```powershell
python run.py
```

AI server:

```text
http://localhost:8000
```

API docs:

```text
http://localhost:8000/docs
```

Start frontend and backend with hot reload:

```powershell
docker compose --env-file .env.docker -f docker-compose.yml -f docker-compose.dev.yml up --build
```

Start in the background:

```powershell
docker compose --env-file .env.docker -f docker-compose.yml -f docker-compose.dev.yml up --build -d
```

Service URLs:

```text
Frontend: http://localhost:5173
Backend:  http://localhost:3001
Swagger:  http://localhost:3001/docs
Health:   http://localhost:3001/ready
AI:       http://localhost:8000
```

### Run Services Manually

Backend:

```powershell
cd backend
copy .env.example .env
npm install
npx prisma migrate dev
npm run prisma:seed
npm run dev
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

AI server:

```powershell
python run.py
```

Skip pre-flight checks if needed:

```powershell
python run.py --no-check
```

Use another port:

```powershell
python run.py --port 8080
```

### Database and Prisma

Prisma schema:

```text
backend/prisma/schema.prisma
```

Main tables:

- `users`
- `meetings`
- `meeting_participants`
- `speakers`
- `transcripts`
- `summaries`
- `meeting_keywords`
- `meeting_files`
- `action_items`
- `user_bookmark_notes`
- `system_logs`

Migration:

```powershell
cd backend
npx prisma migrate dev
```

Seed:

```powershell
npm run prisma:seed
```

Generate Prisma client:

```powershell
npm run prisma:generate
```

Deploy migrations:

```powershell
npm run prisma:deploy
```

### AI Server

Common endpoints:

```text
GET  /health
GET  /health/llm
GET  /models/status
POST /api/transcribe
POST /api/diarize
POST /api/process
POST /api/translate
POST /api/summarize
POST /api/meetings/{meeting_id}/index
POST /api/meetings/{meeting_id}/ask
```

`POST /api/process` is the main upload audio processing pipeline.

### Audio Processing Flow

Transcript-only mode:

```text
Audio upload
  -> Normalize to 16kHz mono WAV
  -> Run chunked STT
  -> Stream transcript segments
  -> Save transcripts with speaker_id = null
  -> Save file metadata
```

Transcript + speaker labels:

```text
Audio upload
  -> Normalize to 16kHz mono WAV
  -> Run diarization
  -> Split audio by speaker segments
  -> Run STT on each segment
  -> Merge transcripts by speaker
  -> Stream segments
  -> Save speakers + transcripts
  -> Save file metadata
```

Low VRAM optimization:

- Do not preload multiple models at the same time.
- Run diarization and STT sequentially.
- Release GPU memory after each step.
- Reduce chunk duration and token budget.
- Fall back to CPU when free GPU memory is too low.

### Realtime Recording

Frontend page:

```text
http://localhost:5173/recording
```

Backend WebSocket:

```text
ws://localhost:3001/ws/recording
```

Flow:

```text
Browser microphone
  -> Audio chunks
  -> WebSocket backend
  -> AI server transcribe/process
  -> transcript_segment event
  -> Render live transcript
```

### RAG Q&A With Chroma

For summary generation or transcript indexing, the system can:

1. Load transcripts by `meetingId`.
2. Split transcripts into smaller chunks.
3. Embed each chunk with the Ollama embedding model.
4. Store embeddings in Chroma.
5. Embed a user's question.
6. Retrieve top-k relevant chunks.
7. Build a prompt with retrieved context.
8. Call the local LLM.

If retrieved chunks do not contain enough information, the LLM must answer:

```text
không đủ thông tin trong transcript
```

Default Chroma directory:

```text
%TEMP%\QLDA_AI_GHI_CUOC_HOP\chroma_meetings
```

Or configure:

```env
CHROMA_DB_DIR=...
```

### Frontend

Main routes:

- `/dashboard`
- `/recording`
- `/upload`
- `/meetings`
- `/meetings/:id`
- `/meetings/new`
- `/meetings/:id/edit`
- `/action-items`
- `/settings`

Important files:

```text
frontend/src/services/api.js
frontend/src/routes/index.jsx
frontend/src/styles/index.css
```

### Backend API

Swagger:

```text
http://localhost:3001/docs
```

Health:

```text
GET /ready
```

Meetings:

```text
GET    /meetings
POST   /meetings
GET    /meetings/:id
PUT    /meetings/:id
DELETE /meetings/:id
```

Transcripts:

```text
GET  /meetings/:meetingId/transcripts
POST /meetings/:meetingId/transcripts
PUT  /transcripts/:id
POST /transcripts/:id/translate
POST /meetings/:meetingId/transcripts/batch-translate
```

Summary and Q&A:

```text
GET  /meetings/:meetingId/summaries
POST /meetings/:meetingId/summaries/generate
POST /meetings/:meetingId/vector-index
POST /meetings/:meetingId/qa
```

Export:

```text
GET /meetings/:id/export/:format
```

Supported export formats:

- `pdf`
- `docx`
- `json`

Transcript view query:

```text
?transcriptView=chunks
?transcriptView=full
```

### Testing

Backend tests:

```powershell
cd backend
npm test
```

API smoke test:

```powershell
cd backend
npm run smoke:test-api
```

Frontend build:

```powershell
cd frontend
npm run build
```

AI LLM test:

```powershell
python scripts/test_ollama_llm.py
```

### Common Docker Commands

Start development:

```powershell
docker compose --env-file .env.docker -f docker-compose.yml -f docker-compose.dev.yml up --build
```

Start in the background:

```powershell
docker compose --env-file .env.docker -f docker-compose.yml -f docker-compose.dev.yml up --build -d
```

Restart frontend:

```powershell
docker compose --env-file .env.docker -f docker-compose.yml -f docker-compose.dev.yml restart frontend
```

Restart backend:

```powershell
docker compose --env-file .env.docker -f docker-compose.yml -f docker-compose.dev.yml restart backend
```

View logs:

```powershell
docker compose --env-file .env.docker -f docker-compose.yml -f docker-compose.dev.yml logs -f backend
docker compose --env-file .env.docker -f docker-compose.yml -f docker-compose.dev.yml logs -f frontend
```

Stop containers:

```powershell
docker compose --env-file .env.docker -f docker-compose.yml -f docker-compose.dev.yml down
```

### Git Push Guide

Remote repository:

```text
https://github.com/vietTNT/QLDA-AI-GHI-CUOC-HOP.git
```

Check current changes:

```powershell
git status --short
```

Stage only the required files:

```powershell
git add README.md .gitignore
```

Review staged changes:

```powershell
git diff --cached
```

Commit:

```powershell
git commit -m "docs: add English README"
```

Push to the current branch:

```powershell
git push origin HEAD
```

If you need to push to `main` explicitly:

```powershell
git push origin HEAD:main
```

Do not commit runtime/generated content such as:

- `.env`
- `.env.docker`
- `node_modules/`
- `frontend/dist/`
- `outputs/`
- `uploads/`
- local model folders
- audio files generated during local testing

### Troubleshooting

Backend container reports `DATABASE_URL not found`:

```env
DOCKER_DATABASE_URL=postgresql://postgres:17122005@host.docker.internal:5432/ai_meeting_assistant?schema=public
DATABASE_URL=postgresql://postgres:17122005@host.docker.internal:5432/ai_meeting_assistant?schema=public
```

Then restart backend:

```powershell
docker compose --env-file .env.docker -f docker-compose.yml -f docker-compose.dev.yml restart backend
```

`python run.py` reports `No module named torch`:

```powershell
.\.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

Ollama is not available:

```powershell
ollama list
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
```

FFmpeg is missing:

```env
FFMPEG_BINARY=C:\path\to\ffmpeg.exe
```

GPU 4 GB out of memory:

```env
AI_LOW_VRAM_MODE=1
PRELOAD_MODELS=0
STT_CHUNK_DURATION=10
STT_MAX_NEW_TOKENS=128
DIARIZATION_DEVICE=cpu
```

### Security and Performance Notes

Security:

- Do not commit `.env` or `.env.docker` with real secrets.
- Change JWT secrets before real deployment.
- Disable `AUTH_DISABLED=true` when real login and authorization are required.
- Restrict CORS with `FRONTEND_ORIGIN`.
- Restrict uploads with `MAX_UPLOAD_MB`.
- Use Helmet and rate limiting on the backend.
- Do not expose the AI server directly to the internet without a proper auth/proxy layer.

Performance:

- PostgreSQL has indexes for common query fields.
- Backend uses soft delete for main entities.
- AI low VRAM mode avoids keeping STT and diarization models in GPU at the same time.
- Chroma should be locked or queued when multiple indexing requests run concurrently.
- For long transcripts, use RAG instead of putting the whole transcript into the LLM prompt.

## Tiếng Việt

Hệ thống AI Meeting Assistant hỗ trợ ghi âm cuộc họp, chuyển giọng nói thành văn bản, phân biệt người nói, dịch Anh - Việt, tóm tắt nội dung, hỏi đáp theo transcript dài bằng RAG, quản lý cuộc họp và theo dõi action items.

## Mục Lục

- [Tổng quan](#tổng-quan)
- [Nghiệp vụ bài toán](#nghiệp-vụ-bài-toán)
- [Tính năng chính](#tính-năng-chính)
- [Kiến trúc hệ thống](#kiến-trúc-hệ-thống)
- [Cấu trúc thư mục](#cấu-trúc-thư-mục)
- [Tech stack](#tech-stack-1)
- [Yêu cầu môi trường](#yêu-cầu-môi-trường)
- [Cấu hình môi trường](#cấu-hình-môi-trường)
- [Chạy dự án bằng Docker](#chạy-dự-án-bằng-docker)
- [Chạy thủ công từng service](#chạy-thủ-công-từng-service)
- [Database và Prisma](#database-và-prisma)
- [AI server](#ai-server-1)
- [Luồng xử lý audio](#luồng-xử-lý-audio)
- [Luồng phân biệt người nói kết hợp STT](#luồng-phân-biệt-người-nói-kết-hợp-stt)
- [Realtime recording](#realtime-recording-1)
- [RAG Q&A với Chroma](#rag-qa-với-chroma)
- [Frontend](#frontend-1)
- [Backend API](#backend-api-1)
- [Export nội dung cuộc họp](#export-nội-dung-cuộc-họp)
- [Kiểm thử](#kiểm-thử)
- [Lệnh Docker thường dùng](#lệnh-docker-thường-dùng)
- [Troubleshooting](#troubleshooting-1)
- [Ghi chú bảo mật và hiệu năng](#ghi-chú-bảo-mật-và-hiệu-năng)

## Tổng quan

Dự án gồm 3 phần chính:

1. `frontend`: giao diện React/Vite cho người dùng thao tác với dashboard, recording, upload audio, meetings, meeting detail và action items.
2. `backend`: REST API Node.js/Express, Prisma ORM, PostgreSQL, Swagger, upload file, export PDF/DOCX/JSON, WebSocket recording bridge.
3. `app`: AI server FastAPI xử lý STT, diarization, translation, summarization, LLM Q&A và vector indexing.

Trong cấu hình Docker hiện tại, Docker chỉ chạy `frontend` và `backend`. PostgreSQL và AI server chạy trực tiếp trên máy host để tận dụng GPU và model local.

## Nghiệp vụ bài toán

Bài toán nghiệp vụ của hệ thống là quản lý toàn bộ vòng đời nội dung cuộc họp: từ ghi âm hoặc upload audio, chuyển thành transcript, phân biệt người nói, tóm tắt nội dung, trích xuất việc cần làm, cho tới tra cứu, hỏi đáp và xuất biên bản.

Hệ thống hướng tới việc thay thế hoặc giảm tối đa công việc ghi biên bản thủ công. Thay vì người tham gia phải vừa họp vừa ghi chú, hệ thống sẽ tiếp nhận audio, xử lý bằng AI, lưu lại nội dung có cấu trúc và cung cấp các công cụ để người dùng chỉnh sửa, xác nhận, quản lý và khai thác lại nội dung cuộc họp.

### Luồng nghiệp vụ chính

```text
Tạo/chọn cuộc họp
  -> Ghi âm trực tiếp hoặc upload audio
  -> Chọn chế độ transcript-only hoặc phân biệt người nói
  -> AI chuyển audio thành transcript
  -> Lưu transcript, speaker, file metadata vào database
  -> Người dùng rà soát và chỉnh sửa nội dung
  -> Tạo summary, keyword, sentiment, action items
  -> Hỏi đáp nội dung cuộc họp bằng LLM + Chroma
  -> Quản lý action items sau cuộc họp
  -> Export biên bản PDF/DOCX/JSON
```

### Các tác nhân nghiệp vụ

- `Người tổ chức cuộc họp`: tạo cuộc họp, upload audio, kiểm tra transcript, export biên bản.
- `Người tham gia cuộc họp`: được gán vào participant list, có thể xuất hiện trong speaker/action item.
- `Người xử lý biên bản`: chỉnh sửa transcript, đổi tên speaker, thêm ghi chú, xác nhận summary.
- `Người quản lý`: theo dõi dashboard, action items, trạng thái cuộc họp và tiến độ công việc.
- `AI service`: xử lý STT, diarization, translation, summary, embedding và Q&A.

### Đối tượng nghiệp vụ chính

- `Meeting`: cuộc họp, là trung tâm của toàn bộ dữ liệu.
- `Meeting File`: file audio/video/transcript được upload.
- `Transcript`: nội dung lời nói đã chuyển thành văn bản theo từng đoạn thời gian.
- `Speaker`: người nói trong cuộc họp, có thể được AI tạo hoặc người dùng chỉnh sửa.
- `Summary`: bản tóm tắt nội dung cuộc họp.
- `Action Item`: công việc phát sinh sau cuộc họp.
- `Keyword`: từ khóa quan trọng được trích xuất từ transcript.
- `Note/Bookmark`: ghi chú hoặc đánh dấu đoạn transcript quan trọng.
- `System Log`: nhật ký thao tác và audit.

### Quy tắc nghiệp vụ quan trọng

- Một cuộc họp có thể có nhiều transcript segments, speakers, summaries, files, action items và notes.
- Nếu người dùng chọn `Transcript only`, hệ thống chỉ chạy STT và không tự tạo speaker.
- Nếu người dùng chọn `Transcript + speaker labels`, hệ thống chạy diarization để tạo/gán speaker cho từng đoạn transcript.
- Người dùng có thể đổi tên speaker hoặc gán lại speaker cho từng chunk sau khi AI xử lý.
- Transcript được lưu theo meeting ID để phục vụ xem lại, tìm kiếm, dịch, summary và Q&A.
- Summary và Q&A phải dựa trên transcript đã lưu, không dựa trên dữ liệu ngoài cuộc họp.
- Với Q&A transcript dài, hệ thống dùng Chroma để truy hồi context liên quan trước khi gọi LLM.
- Nếu context truy hồi không chứa câu trả lời, LLM phải trả lời `không đủ thông tin trong transcript`.
- Action items có trạng thái nghiệp vụ `Todo`, `InProgress`, `Done` và có thể được kéo thả trên board.
- Export biên bản phải phản ánh đúng chế độ người dùng đang xem: `Chunks` hoặc `Full text`.

### Giá trị nghiệp vụ

- Giảm thời gian ghi biên bản thủ công.
- Hạn chế bỏ sót quyết định, nhiệm vụ và thông tin quan trọng.
- Cho phép biết ai nói gì và nói vào thời điểm nào.
- Tự động tạo tóm tắt, keyword và action items.
- Giúp người quản lý theo dõi công việc phát sinh sau cuộc họp.
- Cho phép hỏi đáp lại nội dung cuộc họp dài bằng ngôn ngữ tự nhiên.
- Dễ lưu trữ và chia sẻ biên bản qua PDF, DOCX hoặc JSON.

## Tính năng chính

### Meeting Management

- Tạo, sửa, xóa mềm cuộc họp.
- Xem danh sách cuộc họp.
- Tìm kiếm và lọc cuộc họp.
- Sửa thông tin chi tiết: tiêu đề, mô tả, thời gian bắt đầu/kết thúc, passcode, trạng thái.
- Xem chi tiết theo tab:
  - Transcript
  - Speakers
  - Summary
  - Action Items
  - Files
  - Notes/Bookmarks

### Audio Upload và STT

- Upload audio.
- Chọn chế độ:
  - `Transcript only`: chỉ chạy STT, không tạo speaker.
  - `Transcript + speaker labels`: chạy diarization để phân biệt người nói.
- Stream transcript theo từng chunk trong quá trình xử lý.
- Lưu transcript vào PostgreSQL sau khi xử lý.
- Gán speaker thủ công cho từng chunk.

### Realtime Recording

- Ghi âm từ trình duyệt.
- Stream audio chunk qua WebSocket.
- Nói tới đâu transcript tới đó.
- Hỗ trợ 2 chế độ:
  - Một người nói: chỉ transcript.
  - Nhiều người nói: transcript + diarization.

### Speaker Management

- Thêm speaker.
- Đổi tên speaker.
- Gán speaker cho từng transcript chunk.
- Transcript-only mode không tự tạo speaker giả.

### Translation

- Dịch transcript Việt -> Anh.
- Dịch transcript Anh -> Việt.
- Dùng model local cấu hình trong `app/config.py`.
- Lưu kết quả vào `translated_text`.

### Summary và Q&A

- Tạo summary bằng LLM local.
- Index transcript theo meeting ID vào Chroma.
- Hỏi đáp transcript dài bằng Embeddings + Vector DB:
  - chunk transcript
  - embed từng chunk
  - lưu Chroma
  - embed câu hỏi
  - truy hồi top-k context
  - gọi LLM với prompt ràng buộc
- Nếu retrieved chunks không đủ thông tin, LLM phải trả lời: `không đủ thông tin trong transcript`.

### Action Items

- Board kiểu Trello với 3 cột:
  - Todo
  - In progress
  - Done
- Kéo thả task giữa các cột.
- Thêm task mới.
- Sửa task.
- Lọc theo meeting, assignee, priority.

### Dashboard

- Tổng số cuộc họp.
- Cuộc họp đã hoàn thành.
- Tổng users.
- Tổng action items.
- Action items pending.
- Tổng transcripts.
- Tổng summaries.
- Tổng audio files.
- Analytics: meeting trend, sentiment distribution, speaker distribution, keyword trend, action item statistics.

### Export

- Export nội dung cuộc họp ra:
  - PDF
  - DOCX
  - JSON
- Hỗ trợ tiếng Việt bằng font Unicode.
- Export theo đúng chế độ đang xem ở Meeting Detail:
  - `Chunks`: xuất từng chunk có speaker và timestamp.
  - `Full text`: gom transcript thành một đoạn dài.

## Kiến trúc hệ thống

```text
Browser
  |
  | HTTP / WebSocket
  v
Frontend React/Vite :5173
  |
  | REST API
  v
Backend Node.js/Express :3001
  |
  | Prisma
  v
PostgreSQL :5432

Backend Node.js
  |
  | HTTP multipart / JSON
  v
AI Server FastAPI :8000
  |
  | Local models + Ollama + Chroma
  v
STT / Diarization / Translation / LLM / RAG
```

Backend đóng vai trò API gateway cho frontend và lưu dữ liệu nghiệp vụ vào PostgreSQL. AI server tập trung xử lý model local để tránh trộn logic AI nặng vào backend Node.js.

## Cấu trúc thư mục

```text
.
├── app/                       # FastAPI AI server
│   ├── main.py                # AI API entrypoint
│   ├── config.py              # Cấu hình model, GPU, Ollama, Chroma
│   └── services/              # STT, diarization, pipeline, RAG, translation
├── backend/                   # Node.js Express backend
│   ├── prisma/                # Prisma schema, migrations, seed
│   ├── scripts/               # Smoke test API
│   └── src/
│       ├── config/            # env, prisma client
│       ├── controllers/       # REST controllers
│       ├── docs/              # Swagger/OpenAPI
│       ├── dtos/              # Zod validation schemas
│       ├── middleware/        # auth, validate, upload, error handler
│       ├── repositories/      # Repository layer
│       ├── routes/            # Express routes
│       ├── services/          # Business logic
│       ├── utils/             # logger, errors, jwt, pagination
│       └── websocket/         # Recording WebSocket
├── frontend/                  # React/Vite frontend
│   ├── src/
│   │   ├── components/
│   │   ├── layouts/
│   │   ├── pages/
│   │   ├── routes/
│   │   ├── services/
│   │   └── styles/
├── data/                      # Data runtime, uploads, processed files, Chroma
├── diarization/               # Local diarization model bundle
├── uploads/                   # Upload runtime files
├── docker-compose.yml         # Docker frontend/backend
├── docker-compose.dev.yml     # Hot reload compose override
├── .env.example               # AI server env example
├── .env.docker.example        # Docker env example
├── Dockerfile.ai              # AI Dockerfile tham khảo, hiện không dùng trong compose
└── run.py                     # Script chạy AI server kèm pre-flight checks
```

## Tech stack

### Frontend

- React 18
- Vite
- React Router
- Tailwind CSS
- Axios
- WebSocket browser API

### Backend

- Node.js 22+
- Express.js
- PostgreSQL
- Prisma ORM
- JWT Authentication
- Role-based Authorization
- Zod DTO validation
- Swagger/OpenAPI
- Multer upload
- Winston logger
- Helmet
- CORS
- Rate limiting
- bcrypt
- PDFKit
- docx
- WebSocket `ws`

### AI Server

- Python FastAPI
- PyTorch
- PhoWhisper / STT local model
- Diarization local model
- Local translation models:
  - VI -> EN
  - EN -> VI
- Ollama:
  - `qwen2.5:7b` cho LLM
  - `nomic-embed-text` cho embeddings
- Chroma vector DB
- FFmpeg

## Yêu cầu môi trường

### Bắt buộc

- Node.js `22+`
- npm
- Python `3.10+` hoặc bản tương thích với dependencies AI hiện tại
- PostgreSQL
- Docker Desktop
- FFmpeg
- Ollama

### Khuyến nghị nếu chạy AI bằng GPU

- NVIDIA GPU
- CUDA runtime phù hợp với PyTorch đang cài
- VRAM tối thiểu 4GB
- Bật low VRAM mode:

```env
AI_LOW_VRAM_MODE=1
PRELOAD_MODELS=0
STT_DEVICE=cuda
DIARIZATION_DEVICE=cuda
STT_CHUNK_DURATION=15
STT_MAX_NEW_TOKENS=256
```

## Cấu hình môi trường

### 1. AI server `.env`

Copy file mẫu:

```powershell
copy .env.example .env
```

Các biến quan trọng:

```env
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5:7b
OLLAMA_EMBED_MODEL=nomic-embed-text

STT_MODEL_DIR=C:\Users\ADMIN\PhoWhisper-medium
DIARIZATION_MODEL_DIR=.\diarization\speaker-diarization-community-1
TRANSLATION_VI_EN_DIR=C:\Users\ADMIN\opus-mt-vi-en
TRANSLATION_EN_VI_DIR=C:\Users\ADMIN\opus-mt-en-vi

AI_LOW_VRAM_MODE=1
PRELOAD_MODELS=0
STT_DEVICE=cuda
DIARIZATION_DEVICE=cuda
```

Nếu không set biến model path, `app/config.py` sẽ dùng default local path hiện tại.

### 2. Docker env

Copy file mẫu:

```powershell
copy .env.docker.example .env.docker
```

Nội dung mặc định:

```env
DOCKER_DATABASE_URL=postgresql://postgres:17122005@host.docker.internal:5432/ai_meeting_assistant?schema=public
DOCKER_AI_SERVICE_URL=http://host.docker.internal:8000

DATABASE_URL=postgresql://postgres:17122005@host.docker.internal:5432/ai_meeting_assistant?schema=public
AI_SERVICE_URL=http://host.docker.internal:8000
AUTH_DISABLED=true
```

`host.docker.internal` cho phép container backend gọi PostgreSQL và AI server đang chạy trên máy host.

### 3. Backend `.env`

Nếu chạy backend thủ công:

```powershell
cd backend
copy .env.example .env
```

Ví dụ:

```env
PORT=3001
DATABASE_URL=postgresql://postgres:17122005@localhost:5432/ai_meeting_assistant?schema=public
AI_SERVICE_URL=http://localhost:8000
FRONTEND_ORIGIN=http://localhost:5173
AUTH_DISABLED=true
```

## Chạy dự án bằng Docker

Docker hiện chạy `frontend` và `backend`. Trước khi chạy Docker, cần bật PostgreSQL và AI server trên host.

### Bước 1: chạy AI server

```powershell
python run.py
```

AI server chạy tại:

```text
http://localhost:8000
```

Docs:

```text
http://localhost:8000/docs
```

### Bước 2: đảm bảo PostgreSQL chạy

Database mặc định:

```text
ai_meeting_assistant
```

Kết nối ví dụ:

```text
postgresql://postgres:17122005@localhost:5432/ai_meeting_assistant?schema=public
```

### Bước 3: chạy frontend + backend bằng Docker

Development hot reload:

```powershell
docker compose --env-file .env.docker -f docker-compose.yml -f docker-compose.dev.yml up --build
```

Chạy nền:

```powershell
docker compose --env-file .env.docker -f docker-compose.yml -f docker-compose.dev.yml up --build -d
```

Sau khi chạy:

```text
Frontend: http://localhost:5173
Backend:  http://localhost:3001
Swagger:  http://localhost:3001/docs
Health:   http://localhost:3001/ready
AI:       http://localhost:8000
```

## Chạy thủ công từng service

### Backend

```powershell
cd backend
copy .env.example .env
npm install
npx prisma migrate dev
npm run prisma:seed
npm run dev
```

Backend chạy tại:

```text
http://localhost:3001
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Frontend chạy tại:

```text
http://localhost:5173
```

### AI server

```powershell
python run.py
```

Nếu cần bỏ pre-flight checks:

```powershell
python run.py --no-check
```

Chạy port khác:

```powershell
python run.py --port 8080
```

## Database và Prisma

Prisma schema nằm tại:

```text
backend/prisma/schema.prisma
```

Các bảng chính:

- `users`
- `meetings`
- `meeting_participants`
- `speakers`
- `transcripts`
- `summaries`
- `meeting_keywords`
- `meeting_files`
- `action_items`
- `user_bookmark_notes`
- `system_logs`

Migration:

```powershell
cd backend
npx prisma migrate dev
```

Seed dữ liệu mẫu:

```powershell
npm run prisma:seed
```

Generate Prisma client:

```powershell
npm run prisma:generate
```

Deploy migration trong container/dev compose:

```powershell
npm run prisma:deploy
```

## AI server

AI server xử lý các chức năng:

- STT
- diarization
- transcript-only mode
- translation
- summarization
- LLM Q&A
- vector indexing Chroma
- GPU memory cleanup cho máy VRAM thấp

Các endpoint thường dùng:

```text
GET  /health
GET  /health/llm
GET  /models/status
POST /api/transcribe
POST /api/diarize
POST /api/process
POST /api/translate
POST /api/summarize
POST /api/meetings/{meeting_id}/index
POST /api/meetings/{meeting_id}/ask
```

`POST /api/process` là pipeline chính cho upload audio.

## Luồng xử lý audio

### Transcript only

```text
Audio upload
  -> normalize 16kHz mono WAV
  -> STT theo chunk
  -> stream transcript segment
  -> lưu transcripts với speaker_id = null
  -> lưu file metadata
```

Chế độ này không chạy diarization và không tự tạo speaker.

### Transcript + speaker labels

```text
Audio upload
  -> normalize 16kHz mono WAV
  -> diarization
  -> cắt audio theo speaker segment
  -> STT từng segment
  -> merge transcript theo speaker
  -> stream từng đoạn
  -> lưu speakers + transcripts
  -> lưu file metadata
```

### Tối ưu GPU 4GB

AI server hỗ trợ low VRAM mode:

- Không preload nhiều model cùng lúc.
- Chạy diarization và STT tuần tự.
- Giải phóng GPU memory sau từng bước.
- Giảm chunk duration.
- Giảm max token budget.
- Có fallback CPU khi GPU free memory quá thấp.

Các biến quan trọng:

```env
AI_LOW_VRAM_MODE=1
PRELOAD_MODELS=0
STT_CHUNK_DURATION=15
STT_MAX_NEW_TOKENS=256
DIARIZATION_GPU_MEMORY_LIMIT_MB=900
DIARIZATION_GPU_CUTOFF_RATIO=0.20
DIARIZATION_GPU_CUTOFF_FLOOR_MB=700
```

## Luồng phân biệt người nói kết hợp STT

Trong hệ thống này, phần phân biệt người nói được xây dựng bằng cách kết hợp `diarization` và `PhoWhisper STT`.

Hai thành phần này làm hai việc khác nhau:

```text
Diarization = ai nói vào khoảng thời gian nào
PhoWhisper STT = người đó nói nội dung gì
```

Diarization không chuyển âm thanh thành chữ. Nó chỉ phân tích đặc trưng giọng nói để tạo timeline người nói:

```text
SPEAKER_00  0.00s - 3.74s
SPEAKER_01  3.80s - 7.20s
SPEAKER_00  7.30s - 12.50s
```

PhoWhisper sau đó transcribe từng đoạn audio thành text. Khi ghép hai kết quả lại, hệ thống có được transcript cuối cùng:

```text
SPEAKER_00  0.00s - 3.74s: Xin chào mọi người...
SPEAKER_01  3.80s - 7.20s: Tôi xin báo cáo phần dashboard...
SPEAKER_00  7.30s - 12.50s: Vậy backend còn phần nào chưa xong?
```

### Luồng tổng quát

```text
Audio đầu vào
  -> Chuẩn hóa audio
  -> Chạy diarization
  -> Nhận timeline speaker
  -> Cắt audio theo từng speaker segment
  -> Chạy PhoWhisper STT trên từng segment
  -> Gắn text vào speaker tương ứng
  -> Offset timestamp về timeline gốc
  -> Merge các đoạn gần nhau cùng speaker
  -> Lưu speakers + transcripts vào database
  -> Hiển thị trên Meeting Detail
```

### Bước 1: nhận audio đầu vào

Audio có thể đến từ:

- Upload file audio ở màn Upload Audio.
- Recording realtime từ microphone.

Các định dạng thường gặp:

```text
mp3, wav, m4a, webm
```

Sau khi nhận file, hệ thống đưa audio vào AI pipeline.

### Bước 2: chuẩn hóa audio

Audio được chuyển về định dạng thống nhất:

```text
16kHz
mono
wav
float32
```

Mục đích:

- STT chạy ổn định hơn.
- Diarization nhận input đồng nhất.
- Giảm lỗi codec trên Windows.
- Giảm tải bộ nhớ GPU/CPU.
- Dễ cắt audio theo timestamp.

Ví dụ:

```text
input.m4a
  -> normalized_16k_mono.wav
```

### Bước 3: diarization phân biệt người nói

Diarization trả lời câu hỏi:

```text
Ai đang nói vào khoảng thời gian nào?
```

Nó không biết tên thật của người nói. Nó chỉ tạo nhãn tạm:

```text
SPEAKER_00
SPEAKER_01
SPEAKER_02
```

Ví dụ audio thật:

```text
0s  - 5s   Anh Nam nói
5s  - 9s   Chị Lan nói
9s  - 13s  Anh Nam nói tiếp
13s - 16s  Chị Lan nói tiếp
```

Diarization không biết đó là Anh Nam hay Chị Lan, nhưng nó nhận ra:

```text
0s - 5s và 9s - 13s có giọng giống nhau
5s - 9s và 13s - 16s có giọng giống nhau
```

Kết quả trả về:

```text
SPEAKER_00  0s  - 5s
SPEAKER_01  5s  - 9s
SPEAKER_00  9s  - 13s
SPEAKER_01  13s - 16s
```

Sau khi xử lý xong, người dùng có thể đổi tên:

```text
SPEAKER_00 -> Anh Nam
SPEAKER_01 -> Chị Lan
```

### Diarization phân biệt speaker như thế nào?

Diarization phân biệt người nói bằng cách so sánh đặc trưng giọng nói, không phải bằng nội dung câu nói.

Quy trình bên trong thường gồm các bước:

#### 1. Voice Activity Detection

Model xác định đoạn nào có tiếng người nói, đoạn nào là im lặng hoặc nhiễu.

Ví dụ:

```text
0.00s - 1.20s    im lặng
1.20s - 4.80s    có người nói
4.80s - 5.10s    im lặng
5.10s - 8.00s    có người nói
```

#### 2. Chia audio thành các đoạn nhỏ

Audio được chia thành nhiều đoạn ngắn để phân tích giọng:

```text
1.20s - 2.50s
2.50s - 3.80s
3.80s - 4.80s
5.10s - 6.30s
6.30s - 8.00s
```

#### 3. Trích xuất speaker embedding

Với mỗi đoạn nhỏ, model tạo một vector đặc trưng giọng nói, thường gọi là speaker embedding.

Embedding này mô tả các đặc điểm như:

- âm sắc,
- cao độ,
- năng lượng giọng,
- đặc trưng phổ âm thanh,
- cách phát âm,
- nhịp nói.

Ví dụ minh họa:

```text
Đoạn A -> [0.12, 0.88, 0.31, ...]
Đoạn B -> [0.13, 0.86, 0.30, ...]
Đoạn C -> [0.72, 0.21, 0.94, ...]
```

Nếu hai vector gần nhau, khả năng cao là cùng một người nói.

#### 4. Clustering các đoạn có giọng giống nhau

Model gom các đoạn có speaker embedding giống nhau vào cùng một cụm:

```text
Đoạn 1 -> nhóm A -> SPEAKER_00
Đoạn 2 -> nhóm A -> SPEAKER_00
Đoạn 3 -> nhóm B -> SPEAKER_01
Đoạn 4 -> nhóm A -> SPEAKER_00
```

Kết quả:

```text
SPEAKER_00:
1.20s - 4.80s
9.00s - 12.00s

SPEAKER_01:
5.10s - 8.00s
12.30s - 16.00s
```

#### 5. Tạo speaker timeline

Cuối cùng diarization trả timeline người nói:

```text
SPEAKER_00  1.20s - 4.80s
SPEAKER_01  5.10s - 8.00s
SPEAKER_00  9.00s - 12.00s
SPEAKER_01  12.30s - 16.00s
```

Ý nghĩa:

```text
Giọng ở 1.20s - 4.80s giống giọng ở 9.00s - 12.00s
=> cùng một người
=> SPEAKER_00
```

Diarization không phân biệt trực tiếp theo giới tính. Nó không dùng rule kiểu `giọng trầm = nam`, `giọng cao = nữ`. Nó phân biệt bằng độ giống nhau của đặc trưng giọng nói. Tuy vậy, vì giọng nam và nữ thường khác nhau rõ nên model thường tách dễ hơn.

### Bước 4: cắt audio theo diarization segment

Sau khi có timeline speaker, hệ thống cắt file audio gốc thành các đoạn nhỏ.

Ví dụ:

```text
full_audio.wav
  -> segment_001.wav  0.00s - 3.74s   SPEAKER_00
  -> segment_002.wav  3.80s - 7.20s   SPEAKER_01
  -> segment_003.wav  7.30s - 12.50s  SPEAKER_00
```

Mỗi segment giữ metadata:

```json
{
  "speaker": "SPEAKER_00",
  "start": 0.0,
  "end": 3.74,
  "audio": "segment_001.wav"
}
```

### Bước 5: PhoWhisper STT từng segment

PhoWhisper chạy STT trên từng đoạn audio đã cắt.

Ví dụ:

```text
segment_001.wav -> "Xin chào mọi người, hôm nay chúng ta họp về tiến độ dự án."
segment_002.wav -> "Tôi đã hoàn thành phần giao diện dashboard."
segment_003.wav -> "Tốt, vậy phần backend còn những gì?"
```

Vì mỗi segment đã biết speaker từ diarization, hệ thống gắn text vào đúng speaker:

```json
{
  "speaker": "SPEAKER_00",
  "start": 0.0,
  "end": 3.74,
  "text": "Xin chào mọi người, hôm nay chúng ta họp về tiến độ dự án."
}
```

### Bước 6: offset timestamp về timeline gốc

Khi PhoWhisper transcribe một file segment nhỏ, timestamp nội bộ có thể bắt đầu từ `0s`.

Ví dụ segment gốc bắt đầu tại `30.00s`, PhoWhisper trả:

```text
0.00s - 2.10s
```

Hệ thống cần cộng offset:

```text
30.00s + 0.00s = 30.00s
30.00s + 2.10s = 32.10s
```

Nhờ vậy transcript cuối cùng vẫn đúng theo timeline audio gốc:

```text
SPEAKER_00  30.00s - 32.10s
```

### Bước 7: merge các đoạn gần nhau cùng speaker

Nếu diarization hoặc STT tạo nhiều đoạn nhỏ liên tiếp của cùng một speaker, hệ thống có thể gộp lại.

Trước khi merge:

```text
SPEAKER_00 0.00s - 2.00s: Xin chào mọi người
SPEAKER_00 2.10s - 4.00s: hôm nay chúng ta họp
SPEAKER_01 4.20s - 6.00s: Tôi xin báo cáo
```

Sau khi merge:

```text
SPEAKER_00 0.00s - 4.00s: Xin chào mọi người hôm nay chúng ta họp
SPEAKER_01 4.20s - 6.00s: Tôi xin báo cáo
```

Mục đích:

- Transcript dễ đọc hơn.
- Giao diện ít chunk vụn.
- Export biên bản đẹp hơn.
- Summary và Q&A có context liền mạch hơn.

### Bước 8: lưu vào database

Backend lưu speaker vào bảng `speakers`:

```text
speakers
- id
- meeting_id
- speaker_label: SPEAKER_00
- real_name: null
- color_hex
```

Transcript được lưu vào bảng `transcripts`:

```text
transcripts
- meeting_id
- speaker_id
- start_timestamp
- end_timestamp
- original_text
- translated_text
- sentiment_label
- behavior_label
- is_highlighted
```

Ví dụ kết quả cuối cùng:

```text
SPEAKER_00 | 0.00s - 3.74s | Xin chào mọi người...
SPEAKER_01 | 3.80s - 7.20s | Tôi đã hoàn thành...
```

### Bước 9: hiển thị và chỉnh sửa trên giao diện

Ở Meeting Detail, tab Transcript hiển thị:

```text
SPEAKER_00   0s - 3.74s
Xin chào mọi người...

SPEAKER_01   3.8s - 7.2s
Tôi đã hoàn thành...
```

Người dùng có thể:

- đổi tên speaker,
- thêm speaker,
- gán lại speaker cho từng chunk,
- xem transcript theo chunk,
- xem transcript dạng full text,
- dịch transcript,
- export biên bản.

### Trường hợp diarization dễ sai

Diarization có thể nhầm speaker trong các trường hợp:

- Hai người nói chồng lên nhau.
- Audio nhiều nhiễu hoặc vọng.
- Micro quá xa người nói.
- Một người nói quá ít.
- Hai người có giọng rất giống nhau.
- Có nhạc nền hoặc âm thanh không phải lời nói.
- Đoạn nói quá ngắn.
- Model đoán sai số lượng speaker.
- Một người thay đổi micro hoặc âm lượng giữa chừng.

Vì vậy hệ thống cho phép người dùng chỉnh lại speaker sau khi AI xử lý.

### Chế độ transcript-only khác gì?

Nếu người dùng chọn `Transcript only`, pipeline không chạy diarization:

```text
Audio
  -> normalize
  -> PhoWhisper STT theo chunk
  -> stream transcript segment
  -> lưu transcript với speaker_id = null
```

Khi đó hệ thống không tạo `SPEAKER_00` mặc định. Transcript chỉ là nội dung văn bản theo thời gian, phù hợp với cuộc họp một người nói hoặc khi người dùng không cần phân biệt speaker.

### Tối ưu trên GPU 4GB

Với GPU 4GB, không nên giữ diarization model và PhoWhisper model trên GPU cùng lúc.

Luồng tối ưu:

```text
1. Load diarization model
2. Chạy diarization
3. Giải phóng GPU memory
4. Load PhoWhisper
5. STT từng segment/chunk
6. Giải phóng GPU cache sau chunk hoặc sau job
7. Trả transcript cuối cùng
```

Các cấu hình quan trọng:

```env
AI_LOW_VRAM_MODE=1
PRELOAD_MODELS=0
STT_DEVICE=cuda
DIARIZATION_DEVICE=cuda
STT_CHUNK_DURATION=15
STT_MAX_NEW_TOKENS=256
DIARIZATION_GPU_MEMORY_LIMIT_MB=900
```

Nếu vẫn thiếu VRAM, có thể chuyển diarization sang CPU:

```env
DIARIZATION_DEVICE=cpu
```

## Realtime recording

Frontend page:

```text
http://localhost:5173/recording
```

Backend WebSocket:

```text
ws://localhost:3001/ws/recording
```

Luồng realtime:

```text
Browser microphone
  -> audio chunks
  -> WebSocket backend
  -> AI server transcribe/process
  -> transcript_segment event
  -> render live transcript
```

Người dùng có thể chọn:

- Một người nói: chỉ STT.
- Nhiều người nói: STT + diarization.

## RAG Q&A với Chroma

Khi tạo summary hoặc index transcript, hệ thống có thể:

1. Lấy transcript theo `meetingId`.
2. Chunk transcript thành các đoạn nhỏ.
3. Embed từng chunk bằng Ollama embedding model.
4. Lưu embeddings vào Chroma.
5. Khi hỏi đáp:
   - embed câu hỏi
   - retrieve top-k chunks
   - tạo prompt với context
   - gọi LLM local

Prompt Q&A được siết để tránh bịa:

```text
Nếu retrieved chunks không chứa câu trả lời,
bắt buộc trả: không đủ thông tin trong transcript
```

Chroma directory mặc định:

```text
%TEMP%\QLDA_AI_GHI_CUOC_HOP\chroma_meetings
```

Hoặc cấu hình:

```env
CHROMA_DB_DIR=...
```

## Frontend

Các màn chính:

- `/dashboard`
- `/recording`
- `/upload`
- `/meetings`
- `/meetings/:id`
- `/meetings/new`
- `/meetings/:id/edit`
- `/action-items`
- `/settings`

Frontend service API nằm tại:

```text
frontend/src/services/api.js
```

Routing:

```text
frontend/src/routes/index.jsx
```

Global CSS:

```text
frontend/src/styles/index.css
```

## Backend API

Swagger:

```text
http://localhost:3001/docs
```

Health:

```text
GET /ready
```

### Meetings

```text
GET    /meetings
POST   /meetings
GET    /meetings/:id
PUT    /meetings/:id
DELETE /meetings/:id
```

### Participants

```text
GET    /meetings/:meetingId/participants
POST   /meetings/:meetingId/participants
PUT    /participants/:meetingId/:userId
DELETE /participants/:meetingId/:userId
```

### Speakers

```text
GET   /meetings/:meetingId/speakers
POST  /meetings/:meetingId/speakers
PATCH /speakers/:id
```

### Transcripts

```text
GET  /meetings/:meetingId/transcripts
POST /meetings/:meetingId/transcripts
PUT  /transcripts/:id
POST /transcripts/:id/translate
POST /meetings/:meetingId/transcripts/batch-translate
```

### Summary và Q&A

```text
GET  /meetings/:meetingId/summaries
POST /meetings/:meetingId/summaries/generate
POST /meetings/:meetingId/vector-index
POST /meetings/:meetingId/qa
```

### Action Items

```text
GET   /meetings/:meetingId/action-items
POST  /meetings/:meetingId/action-items
PUT   /action-items/:id
PATCH /action-items/:id/complete
```

### Files

```text
GET    /meetings/:meetingId/files
POST   /meetings/:meetingId/files/audio
POST   /meetings/:meetingId/files/video
POST   /meetings/:meetingId/files/transcript
GET    /files/:id/download
DELETE /files/:id
```

### Dashboard

```text
GET /dashboard/overview
GET /dashboard/analytics
```

### Export

```text
GET /meetings/:id/export/:format
```

`format`:

- `pdf`
- `docx`
- `json`

Query:

```text
?transcriptView=chunks
?transcriptView=full
```

## Export nội dung cuộc họp

Ví dụ export PDF theo chunk:

```text
GET /meetings/{meetingId}/export/pdf?transcriptView=chunks
```

Ví dụ export PDF dạng full text:

```text
GET /meetings/{meetingId}/export/pdf?transcriptView=full
```

PDF dùng font Unicode để hiển thị tiếng Việt đúng. Trong Docker backend đã cài `ttf-dejavu` và backend tự đăng ký:

- `DejaVuSans`
- `DejaVuSans-Bold`

DOCX dùng font `Arial`.

## Kiểm thử

### Backend test

```powershell
cd backend
npm test
```

### Smoke test API

```powershell
cd backend
npm run smoke:test-api
```

### Frontend build

```powershell
cd frontend
npm run build
```

Nếu chạy trong môi trường sandbox bị lỗi `spawn EPERM` khi Vite gọi esbuild, chạy command trực tiếp trong terminal máy hoặc cấp quyền chạy ngoài sandbox.

### AI LLM test

```powershell
python scripts/test_ollama_llm.py
```

## Lệnh Docker thường dùng

### Start development

```powershell
docker compose --env-file .env.docker -f docker-compose.yml -f docker-compose.dev.yml up --build
```

### Start nền

```powershell
docker compose --env-file .env.docker -f docker-compose.yml -f docker-compose.dev.yml up --build -d
```

### Restart frontend

```powershell
docker compose --env-file .env.docker -f docker-compose.yml -f docker-compose.dev.yml restart frontend
```

### Restart backend

```powershell
docker compose --env-file .env.docker -f docker-compose.yml -f docker-compose.dev.yml restart backend
```

### Xem logs

```powershell
docker compose --env-file .env.docker -f docker-compose.yml -f docker-compose.dev.yml logs -f backend
docker compose --env-file .env.docker -f docker-compose.yml -f docker-compose.dev.yml logs -f frontend
```

### Dừng container

```powershell
docker compose --env-file .env.docker -f docker-compose.yml -f docker-compose.dev.yml down
```

### Dọn Docker khi đầy ổ đĩa

Xem dung lượng:

```powershell
docker system df
```

Dọn cache build không dùng:

```powershell
docker builder prune
```

Dọn image/container không dùng:

```powershell
docker system prune
```

Không dùng `docker system prune -a --volumes` nếu chưa chắc chắn, vì có thể xóa volume chứa dữ liệu cần giữ.

## Troubleshooting

### Backend container báo `DATABASE_URL not found`

Kiểm tra `.env.docker` có các biến:

```env
DOCKER_DATABASE_URL=postgresql://postgres:17122005@host.docker.internal:5432/ai_meeting_assistant?schema=public
DATABASE_URL=postgresql://postgres:17122005@host.docker.internal:5432/ai_meeting_assistant?schema=public
```

Sau đó restart backend:

```powershell
docker compose --env-file .env.docker -f docker-compose.yml -f docker-compose.dev.yml restart backend
```

### `python run.py` báo `No module named torch`

Nguyên nhân thường là đang chạy sai Python interpreter. `run.py` đã cố tự relaunch vào `.venv`, nhưng nếu `.venv` chưa có hoặc thiếu dependency:

```powershell
.\.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

### Ollama không kết nối được

Kiểm tra Ollama:

```powershell
ollama list
```

Pull model nếu thiếu:

```powershell
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
```

### AI server không thấy FFmpeg

Cài FFmpeg và đảm bảo `ffmpeg.exe` nằm trong `PATH`, hoặc cấu hình biến môi trường:

```env
FFMPEG_BINARY=C:\path\to\ffmpeg.exe
```

### GPU 4GB bị OOM

Giữ cấu hình:

```env
AI_LOW_VRAM_MODE=1
PRELOAD_MODELS=0
STT_CHUNK_DURATION=15
STT_MAX_NEW_TOKENS=256
```

Nếu vẫn OOM:

```env
DIARIZATION_DEVICE=cpu
```

Hoặc giảm thêm:

```env
STT_CHUNK_DURATION=10
STT_MAX_NEW_TOKENS=128
```

### Transcript-only vẫn có speaker

Transcript-only mode phải lưu `speaker_id = null`. Nếu dữ liệu cũ đã tạo speaker, hãy upload lại với mode `Transcript only` và bật replace transcript nếu UI/API hỗ trợ.

### PDF tiếng Việt bị lỗi font

Đảm bảo backend Docker image đã rebuild sau khi cài font:

```powershell
docker compose --env-file .env.docker -f docker-compose.yml -f docker-compose.dev.yml up --build -d backend
```

Sau đó export lại PDF mới. File PDF cũ đã tạo sai font sẽ không tự sửa.

### Dropdown khó đọc

Dropdown đã được set global CSS trong:

```text
frontend/src/styles/index.css
```

Nếu chưa thấy, reload frontend:

```powershell
docker compose --env-file .env.docker -f docker-compose.yml -f docker-compose.dev.yml restart frontend
```

## Ghi chú bảo mật và hiệu năng

### Bảo mật

- Không commit `.env`, `.env.docker` chứa thông tin thật.
- Đổi JWT secrets trước khi deploy thật.
- Tắt `AUTH_DISABLED=true` khi cần đăng nhập/phân quyền thật.
- Giới hạn CORS bằng `FRONTEND_ORIGIN`.
- Giới hạn upload bằng `MAX_UPLOAD_MB`.
- Dùng Helmet và rate limiting ở backend.
- Không expose trực tiếp AI server ra internet nếu chưa có auth/proxy phù hợp.

### Hiệu năng

- PostgreSQL đã có index cho các trường thường query như meeting status, transcript meeting/timestamp, sentiment, deletedAt.
- Backend dùng soft delete cho các entity chính.
- AI low VRAM mode giúp tránh giữ STT và diarization cùng lúc trong GPU.
- Chroma nên được lock/queue khi index nhiều request đồng thời.
- Với transcript dài, dùng RAG thay vì nhét toàn bộ transcript vào prompt LLM.

## Tài khoản và đăng nhập

Hiện hệ thống đang cấu hình:

```env
AUTH_DISABLED=true
```

Nghĩa là frontend không dùng login/register trong luồng chính. Backend vẫn giữ sẵn module auth/JWT/role để có thể bật lại sau.

## Ghi chú phát triển

Khi sửa code frontend/backend trong Docker dev mode, source được mount vào container nên thường không cần build lại image. Chỉ cần restart container nếu dev server chưa tự reload:

```powershell
docker compose --env-file .env.docker -f docker-compose.yml -f docker-compose.dev.yml restart frontend
docker compose --env-file .env.docker -f docker-compose.yml -f docker-compose.dev.yml restart backend
```

Khi sửa Dockerfile, dependencies hoặc package lock, nên build lại:

```powershell
docker compose --env-file .env.docker -f docker-compose.yml -f docker-compose.dev.yml up --build -d
```
