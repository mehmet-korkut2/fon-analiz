# Fon Analiz Platformu

Yatırım fonlarını analiz eden, karşılaştıran ve risk profiline göre öneri sunan web uygulaması (bitirme projesi).

## Proje yapısı

```
fon-analiz/
├── backend/            FastAPI (Python)
│   ├── app/
│   │   ├── main.py         uygulama girişi
│   │   ├── config.py       ayarlar (.env)
│   │   ├── database.py     veritabanı bağlantısı
│   │   ├── models.py       tablolar (funds, prices)
│   │   ├── schemas.py      API veri modelleri
│   │   ├── routers/        endpoint'ler
│   │   └── services/       iş mantığı (metrikler)
│   ├── scripts/        TEFAS veri toplayıcı (2. aşama)
│   ├── tests/          pytest testleri
│   └── requirements.txt
└── frontend/           React + Vite
    └── src/
        ├── api/            backend istemcisi
        └── pages/          sayfalar
```

## Gereksinimler

- Python 3.12 veya 3.13
- Node.js 20 veya üzeri
- Git

## Kurulum (Windows)

### Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

API: http://localhost:8000/api/health
Swagger: http://localhost:8000/docs

### Frontend (yeni terminalde)

```powershell
cd frontend
npm install
npm run dev
```

Site: http://localhost:5173

### Testler

```powershell
cd backend
.venv\Scripts\activate
pytest
```
