# Sql_Odev

Python ve SQLite kullanılarak hazırlanmış role-based bir havayolu yönetim sistemi demo uygulaması.

## Genel Yapı

- Uygulama ilk açılışta `setup.sql` dosyasını çalıştırarak `airline.db` veritabanını kurar.
- İki ayrı giriş akışı vardır: `Passenger` ve `Admin`.
- Girişler artık şifre kontrollüdür (`Auth_Accounts` tablosu).
- Passenger ekranı uçuş arama, rezervasyon talebi oluşturma ve kendi taleplerini takip etme işlemlerini içerir.
- Admin ekranı uçuş yönetimi, `Countries` CRUD, `Airport` CRUD, `Route` CRUD, `Airplane_type` CRUD, `AirFare` CRUD ve işlem (transaction) takibini içerir.
- Login ekranından yeni `Passenger` hesabı oluşturulabilir.
- Uygulama artık doğrudan ER diyagramındaki ana tablolara (`Flight`, `Route`, `Passengers`, `Employees`, `Transactions`, `AirFare`, `Airplane_type`, `Airport`, `Countries`) bağlı çalışır.

## Çalıştırma

```bash
python3 app.py
```

Tkinter desteği Python kurulumunda yoksa uygulama açılmaz. Böyle bir durumda sistem paketini kurmanız gerekir.

## Login Bilgileri

- Sistem iki rol ile giriş yapar: `Passenger` ve `Admin`.
- Her iki rol de şifre ile doğrulanır (`Auth_Accounts`).
- Seed (hazır) hesaplar için varsayılan şifre: `1234`.
- Login ekranından yeni `Passenger` hesabı oluşturabilirsiniz.

## Temiz Test (Reset)

Eğer daha önce oluşturulmuş eski bir veritabanı dosyası varsa yeni şema veya seed veriler tam görünmeyebilir.

Temiz kurulum için:

```bash
rm -f airline.db
python3 app.py
```

Bu işlemden sonra uygulama `setup.sql` dosyasını baştan çalıştırarak veritabanını yeniden oluşturur.

## Veritabanı

Şema ve seed verileri [setup.sql](setup.sql) içinde tanımlıdır. Veritabanı dosyası otomatik oluşturulur; ayrıca elle kurulum yapmanız gerekmez.
Seed kullanıcıların varsayılan şifresi `1234` olarak ayarlanmıştır.

## Rapor

Detaylı açıklama ve ER diyagramı için [Yeni_Proje_Raporu.md](Yeni_Proje_Raporu.md) dosyasına bakabilirsiniz.
