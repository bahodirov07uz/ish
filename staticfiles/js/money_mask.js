document.addEventListener('input', function (e) {
    if (e.target.classList.contains('mask-money')) {
        let input = e.target;
        let value = input.value.replace(/\s+/g, ''); // Barcha bo'shliqlarni olib tashlash
        
        // Agar kiritilgan narsa raqam bo'lmasa, uni tozalash
        if (isNaN(value)) {
            input.value = value.replace(/\D/g, '');
            return;
        }

        // Kursor pozitsiyasini hisoblash (formatlashdan keyin kursor joyida qolishi uchun)
        let cursorPosition = input.selectionStart;
        let oldLength = input.value.length;

        // Raqamlarni 3 tadan ajratish
        let formattedValue = value.replace(/\B(?=(\d{3})+(?!\d))/g, " ");
        
        input.value = formattedValue;

        // Kursorni qayta joyiga qo'yish
        let newLength = input.value.length;
        cursorPosition = cursorPosition + (newLength - oldLength);
        input.setSelectionRange(cursorPosition, cursorPosition);
    }
});

// Bazaga yuborishdan oldin bo'shliqlarni tozalash (Xatolikni oldini olish)
document.addEventListener('submit', function (e) {
    document.querySelectorAll('.mask-money').forEach(function (input) {
        input.value = input.value.replace(/\s+/g, '');
    });
});