# Bangun Model Prediksi: Fraud Rekening & Sentimen Ulasan

| Kasus | Notebook | Model tersimpan | Skor validasi |
|---|---|---|---|
| A. Deteksi penipuan buka rekening | `notebooks/kasus_a_fraud.ipynb` | `models/kasus_a_fraud_lgbm.joblib` | **TPR @ FPR 5% = 0.582** (ROC-AUC 0.912) |
| B. Sentimen ulasan Video Games | `notebooks/kasus_b_sentimen.ipynb` | `models/kasus_b_sentimen_tfidf_logreg.joblib` | **macro-F1 = 0.939** (F1 neg 0.901, pos 0.978) |

## Kasus A: Bank Account Fraud (Base, bulan 0-3)
- **Metode**: LightGBM (gradient boosting tree), `scale_pos_weight=10`, kolom teks sebagai fitur kategorikal. `device_fraud_count` dibuang (nilainya konstan), `month` tidak dipakai sebagai fitur.
- **Alasan**: data tabular campuran numerik dan kategorikal; boosting tree adalah baseline terkuat di paper BAF, cepat di CPU, tidak perlu scaling, dan menangani kategori serta nilai kosong (`-1`) secara bawaan. Penipu hanya ~1%, sehingga bobot kelas dinaikkan.
- **Pembagian data**: berdasarkan waktu. Latih = bulan 0-2 (397.039 baris), validasi = bulan 3 (150.936 baris). Model di produksi menilai pengajuan yang datang sesudah data latih, jadi split per waktu lebih jujur daripada split acak. Jumlah pohon (445) dipilih dengan early stopping memakai bulan 2 sebagai holdout di dalam data latih, sehingga bulan 3 tidak tersentuh sampai evaluasi akhir.
- **Skor**: dari 1.392 penipu di bulan 3, 58,2% tertangkap saat nasabah jujur yang tertandai dibatasi 5%. Threshold skor untuk FPR 5% ikut disimpan di file model.

## Kasus B: Amazon Reviews 2023, Video_Games (sampai 31 Des 2019)
- **Data**: file `.jsonl.gz` dibaca per baris (tidak dimuat utuh). Input = judul + teks ulasan. Rating 1-2 = negatif, 4-5 = positif, 3 dibuang. Total 2.813.797 ulasan.
- **Metode**: TF-IDF kata dan bigram (300 ribu fitur, `sublinear_tf`) + Logistic Regression dengan `class_weight="balanced"`.
- **Alasan**: baseline kuat untuk sentimen, frasa seperti "not worth" atau "waste of" sudah sangat informatif. Dilatih dalam ~2 menit di CPU untuk jutaan teks dan mudah dijelaskan. Bobot kelas seimbang karena ~82% ulasan positif, sementara macro-F1 menuntut kelas negatif sama pentingnya.
- **Pembagian data**: berdasarkan waktu. Latih = ulasan sampai 2018 (sampel acak 1 juta dari ~2,4 juta agar muat di RAM 16 GB, proporsi kelas tetap), validasi = semua ulasan 2019 (421.794). Ini meniru pemakaian nyata: model menilai ulasan baru.
- **Skor**: macro-F1 0,939 di 2019. Recall negatif 0,953, jadi hampir semua keluhan tertangkap.

## Cara menjalankan
```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```
1. Kasus A: unduh `Base.csv` dari [Kaggle BAF](https://www.kaggle.com/datasets/sgpjesus/bank-account-fraud-dataset-neurips-2022) ke `data/Base.csv`.
2. Kasus B: notebook mengunduh `data/Video_Games.jsonl.gz` (~800 MB) otomatis bila belum ada.
3. Jalankan notebook dari atas ke bawah (Kasus A ~1 menit, Kasus B ~2-3 menit). Setiap notebook menyimpan model lalu memuatnya ulang untuk memastikan hasilnya sama.

Folder `data/` tidak di-commit karena ukurannya besar.
