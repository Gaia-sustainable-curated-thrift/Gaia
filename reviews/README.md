# Review & Rating — GAIA

Penanggung jawab: Keisha Janice Maulina Napitupulu.

## Fitur

- CRUD review dengan rating 1–5, judul, komentar, dan pilihan anonim.
- Pilihan aspek layanan seller.
- Rata-rata rating, distribusi bintang, filter, sorting, dan pagination.
- Interaksi AJAX dengan perlindungan CSRF.
- Edit dan hapus hanya untuk pembuat review; review diri sendiri ditolak.
- Helpful, balasan seller, dan laporan review untuk admin.
- Tampilan responsif mengikuti desain GAIA.

## Batas Integrasi

Halaman review tersedia di `/reviews/seller/<seller_id>/`.
Halaman review seller yang login tersedia di `/reviews/account/`.

Integrasi menu sidebar akun dan rating pada detail produk ditunda.
Template kedua modul tersebut tetap mengikuti versi kelompok dari main.

Verifikasi transaksi selesai belum diterapkan pada modul review,
sehingga tidak ada badge Verified buyer.

## Menjalankan

Jalankan dari root proyek:

```powershell
.\env\Scripts\python.exe manage.py migrate
.\env\Scripts\python.exe manage.py runserver
```

## Pengujian

Tes backend:

```powershell
.\env\Scripts\python.exe manage.py test reviews --noinput
```

Dependency dan tes browser:

```powershell
.\env\Scripts\python.exe -m pip install -r reviews/requirements-dev.txt
$env:GAIA_TEST_BROWSER = "C:\Program Files\Google\Chrome\Application\chrome.exe"
.\env\Scripts\python.exe manage.py test reviews.e2e --noinput
```

Tes menggunakan database pengujian. Catatan TDD tersedia di [TDD.md](TDD.md).

## Data Demo Opsional

Gunakan ID seller yang sudah memiliki produk:

```powershell
.\env\Scripts\python.exe manage.py seed_reviews --seller 1 --count 50
```

Data diberi label [Demo] dan tidak digandakan saat perintah dijalankan ulang.
Menambahkan 50 review tidak otomatis menambahkan 50 produk.