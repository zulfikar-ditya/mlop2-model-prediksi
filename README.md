# Bangun Model Prediksi: Deteksi Penipuan Pembukaan Rekening (Kasus A)

Kasus A dipilih karena digit terakhir NIM (6) bukan bilangan prima.

| Notebook | Model tersimpan | Skor validasi |
|---|---|---|
| `notebooks/kasus_a_fraud.ipynb` | `models/kasus_a_fraud_lgbm.joblib` | **TPR @ FPR 5% = 0.582** (ROC-AUC 0.912) |

## Data
Bank Account Fraud (BAF) varian Base, hanya baris `month` 0-3 (547.975 pengajuan, ~1% penipuan). Kolom `device_fraud_count` dibuang karena nilainya konstan, dan `month` hanya dipakai untuk membagi data, bukan sebagai fitur.

## Metode
LightGBM (gradient boosting tree) dengan `scale_pos_weight=10`. Lima kolom teks (`payment_type`, `employment_status`, `housing_status`, `source`, `device_os`) dipakai sebagai fitur kategorikal.

## Alasan memilih
- Data tabular campuran numerik dan kategorikal. Boosting tree biasanya terbaik untuk jenis data ini dan merupakan baseline terkuat di paper BAF.
- Cepat dilatih di CPU untuk ratusan ribu baris, tidak perlu scaling, dan menangani kategori serta nilai kosong (`-1`) secara bawaan.
- Penipu hanya ~1% data, jadi bobot kelas penipu dinaikkan. TPR@FPR hanya bergantung pada urutan skor, sehingga bobot ini tidak merusak evaluasi.

## Cara membagi data
Berdasarkan waktu: **latih = bulan 0-2** (397.039 baris), **validasi = bulan 3** (150.936 baris).
- Di produksi model dilatih dengan data lama lalu menilai pengajuan yang datang sesudahnya. Split acak mencampur bulan yang sama di latih dan validasi, sehingga skornya terlalu optimis dan tidak menangkap pergeseran pola penipuan antar bulan.
- Jumlah pohon (445) dipilih dengan early stopping (metrik AUC) memakai bulan 2 sebagai holdout di dalam data latih. Dengan begitu bulan 3 tidak tersentuh sampai evaluasi akhir.

## Skor di data validasi (bulan 3)
- **TPR @ FPR 5% = 0,582**: dari 1.392 penipu di bulan 3, 58,2% tertangkap saat nasabah jujur yang salah tertandai dibatasi 5%.
- ROC-AUC = 0,912.
- Threshold skor yang menghasilkan FPR 5% ikut disimpan di file model (`threshold_fpr5`).

## Cara menjalankan
```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```
1. Unduh `Base.csv` dari [Kaggle BAF](https://www.kaggle.com/datasets/sgpjesus/bank-account-fraud-dataset-neurips-2022) ke `data/Base.csv`. Folder `data/` tidak di-commit karena ukurannya besar.
2. Jalankan `notebooks/kasus_a_fraud.ipynb` dari atas ke bawah (~1 menit). Notebook menyimpan model ke `models/`, lalu memuatnya ulang untuk memastikan hasilnya sama.

## Verifikasi inferensi .joblib
Input: 29 fitur model (dari `--input` JSON atau sampel bulan 3 `Base.csv`). Output bisa diatur lewat `--threshold` dan `--fields`.
```bash
python scripts/verify_inference.py --rows 6
python scripts/verify_inference.py --input samples/request.json --threshold 0.5 --fields fraud_score,is_fraud
```

## Backend service
FastAPI, endpoint `POST /predict`, dilindungi header `x-api-key` (nilai dari env `API_KEY`, contoh di `.env.example`).
- Parameter: 29 fitur. Wajib semua, kecuali `prev_address_months_count`, `current_address_months_count`, `bank_months_count`, `session_length_in_minutes`, `device_distinct_emails_8w` yang opsional dan default `-1` (penanda nilai kosong di dataset BAF).
- Response: `model_name`, `model_version` (12 karakter awal SHA-256 file model), `fraud_score`, `is_fraud`, `threshold`. Bisa diatur lewat query `?threshold=0.5` dan `?fields=fraud_score,is_fraud`.
```bash
API_KEY=change-me uvicorn app.main:app --reload
curl -X POST localhost:8000/predict -H "x-api-key: change-me" -H "Content-Type: application/json" -d @samples/request.json
pytest
```
