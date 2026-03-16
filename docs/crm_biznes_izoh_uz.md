# CRM tizimi: dasturchi bo'lmaganlar uchun izoh (UZ)

**Tizim nima qiladi**
- Ishchilarni va ularning ishlari (ish topshiriqlari)ni yuritadi.
- Mahsulotlar va ombor qoldigini ko'rsatadi.
- Sotuvlarni, xaridorlarni, kirim va chiqimlarni hisoblaydi.

**Kim nima qila oladi (umumiy)**
- Admin: yangi ishchi, ish berish, sotuv o'chirish, chiqimlar, sozlamalar.
- Oddiy foydalanuvchi: ro'yxatlar va tafsilotlarni ko'rish.

**Asosiy sahifalar**
- Bosh sahifa: oy bo'yicha umumiy raqamlar.
- Ishchilar: ishchilar ro'yxati va oylik holati.
- Ish qo'shish: ishlab chiqarish jarayonini yozish.
- Mahsulotlar: mavjud mahsulotlar va qoldiq.
- Sotuvlar: sotuv yaratish va ro'yxat.
- Xaridorlar: xaridorlar bazasi va xarid tarixi.
- Kirimlar: sotuvdan tushgan pul.
- Chiqimlar: xarajatlar va xomashyo kirimi.

**Har bir funksiya (oddiy tilda)**
- `HomeView`ish`: ishchining shu oy ishlagan pullarini yopadi va arxivlaydi.
- `yangi_oy_boshlash`: ishchi uchun yangi oy ochadi.
- `EmployeeView`: ishchilar ro'yxatini ko'rsatadi.
- `EmployeeCreateView`: yangi ishchi qo'shadi.
- `EmployeeD: bosh sahifada foyda, chiqim, ishchi soni va qoldiqni ko'rsatadi.
- `oylik_yopeleteView`: ishchini o'chiradi.
- `EmployeeUpdateView`: ishchi ma'lumotini yangilaydi.
- `EmployeeDetailView`: ishchi tafsilotlari, ishlar va avanslarni ko'rsatadi.
- `ProductsView`: mahsulotlar ro'yxatini ko'rsatadi.
- `IshQoshishView`: ishchiga ish biriktiradi va xomashyo sarfini yozadi.
- `SotuvQoshish`: sotuvlar ro'yxatini va sotuv yaratish formasini beradi.
- `SotuvListView`: sotuvlarni filtrlab ko'rsatadi.
- `SotuvDetailView`: bitta sotuv tafsilotlarini ko'rsatadi.
- `sotuv_pdf`: sotuvni PDF chek qilib yuklab beradi.
- `sotuv_qoshish`: yangi sotuvni yaratadi (bir yoki bir nechta mahsulot bilan).
- `sotuv_item_qoshish`: mavjud sotuvga yana mahsulot qo'shadi.
- `sotuv_item_tahrirlash`: sotuvdagi mahsulot narxi yoki miqdorini o'zgartiradi.
- `sotuv_item_ochirish`: sotuvdagi bitta mahsulotni o'chiradi.
- `sotuv_ochirish`: butun sotuvni o'chiradi.
- `get_variant_info`: mahsulot varianti narxi va ombor qoldigini qaytaradi.
- `KirimListView`: kirimlar ro'yxati va statistikasi.
- `XaridorListView`: xaridorlar ro'yxati.
- `XaridorDetailView`: xaridorning sotuv tarixi va jami xaridi.
- `xaridor_qoshish`: yangi xaridor qo'shadi.
- `xaridor_tahrirlash`: xaridor ma'lumotini yangilaydi.
- `ChiqimListView`: chiqimlar ro'yxati va umumiy chiqimni ko'rsatadi.
- `chiqim_ochirish`: chiqim yozuvini o'chiradi.

**Ish berish jarayonidagi farqlar**
- Zakatovka: kroy xomashyosi bo'lsa undan kamayadi; bo'lmasa mustaqil ish sifatida yoziladi.
- Kroy/Rezak: teri sarflari yoziladi, astar bo'lsa kamayadi; jarayon xomashyosi ko'payadi.
- Kosib: padoj majburiy, zakatovka bo'lsa kamayadi; tayyor mahsulot varianti omborga qo'shiladi.
- Boshqa turlar: faqat ish yozuvi yaratiladi.

**Biznes qoidalar (muhim natijalar)**
- Sotuv yaratilsa, ombordagi mahsulot kamayadi va kirim (tushum) yozuvi yaratiladi.
- Sotuvdagi mahsulot miqdori oshsa, ombordagi qoldiq yana kamayadi.
- Sotuvdagi mahsulot miqdori kamaytirilsa, ombordagi qoldiq qaytariladi.
- Sotuvdagi mahsulot o'chirilsa, ombordagi qoldiq qaytariladi.
- Butun sotuv o'chirilsa, ichidagi hamma mahsulotlar qaytariladi.
- Ishchi uchun oylik yopilsa, shu oy ishlari arxivga o'tadi.
- Teri sarfi yozilganda hozirgi kodda ombor qoldigi kamaymaydi, faqat sarf yozuvi yaratiladi.

**Rol va ruxsatlar haqida eslatma**
- Admin bo'lmagan foydalanuvchi ba'zi amallarni bajara olmaydi.
- Tizim ruxsatlarni URL nomi va login holati orqali tekshiradi.
