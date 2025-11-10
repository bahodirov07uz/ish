let products = [
    { id: 1, name: "Noutbuk HP", price: 5500000, quantity: 15, category: "Elektronika", description: "Yuqori sifatli noutbuk" },
    { id: 2, name: "Telefon Samsung", price: 3200000, quantity: 25, category: "Elektronika", description: "Zamonaviy smartfon" },
    { id: 3, name: "Stol", price: 800000, quantity: 8, category: "Mebel", description: "Yog'och stol" },
    { id: 4, name: "Kreslo", price: 650000, quantity: 12, category: "Mebel", description: "Ofis uchun kreslo" }
];

let employees = [
    { id: 1, name: "Aziz Rahimov", phone: "+998 90 123 45 67", position: "Menejer", salary: 4500000, status: "active", email: "aziz@example.com" },
    { id: 2, name: "Dilshod Karimov", phone: "+998 91 234 56 78", position: "Sotuvchi", salary: 3500000, status: "active", email: "dilshod@example.com" },
    { id: 3, name: "Malika Yusupova", phone: "+998 93 345 67 89", position: "Buxgalter", salary: 4000000, status: "active", email: "malika@example.com" },
    { id: 4, name: "Jasur Toshmatov", phone: "+998 94 456 78 90", position: "Ombor mudiri", salary: 3800000, status: "inactive", email: "jasur@example.com" }
];

let currentPage = 'dashboard';
let editingProductId = null;
let editingEmployeeId = null;

function initApp() {
    setupTheme();
    setupNavigation();
    setupModals();
    setupForms();
    updateDashboard();
    renderProducts();
    renderEmployees();
}

function setupTheme() {
    const theme = localStorage.getItem('theme') || 'light';
    document.documentElement.classList.toggle('dark', theme === 'dark');
    
    const themeToggle = document.getElementById('themeToggle');
    const themeToggleMobile = document.getElementById('themeToggleMobile');
    const themeText = document.getElementById('themeText');
    
    function updateThemeText() {
        const isDark = document.documentElement.classList.contains('dark');
        themeText.textContent = isDark ? "Yorug' rejim" : "Qorong'i rejim";
    }
    
    updateThemeText();
    
    function toggleTheme() {
        document.documentElement.classList.toggle('dark');
        const newTheme = document.documentElement.classList.contains('dark') ? 'dark' : 'light';
        localStorage.setItem('theme', newTheme);
        updateThemeText();
    }
    
    themeToggle.addEventListener('click', toggleTheme);
    themeToggleMobile.addEventListener('click', toggleTheme);
}

function setupNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    const menuToggle = document.getElementById('menuToggle');
    const sidebar = document.getElementById('sidebar');
    const pageTitle = document.getElementById('pageTitle');
    
    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const page = item.dataset.page;
            
            navItems.forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');
            
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            document.getElementById(page + 'Page').classList.add('active');
            
            const titles = {
                dashboard: 'Bosh sahifa',
                products: 'Mahsulotlar',
                employees: 'Ishchilar'
            };
            pageTitle.textContent = titles[page] || 'Bosh sahifa';
            
            currentPage = page;
            
            if (window.innerWidth < 768) {
                sidebar.classList.remove('active');
            }
        });
    });
    
    menuToggle.addEventListener('click', () => {
        sidebar.classList.toggle('active');
    });
    
    document.addEventListener('click', (e) => {
        if (window.innerWidth < 768 && 
            !sidebar.contains(e.target) && 
            !menuToggle.contains(e.target) &&
            sidebar.classList.contains('active')) {
            sidebar.classList.remove('active');
        }
    });
}

function setupModals() {
    const productModal = document.getElementById('productModal');
    const employeeModal = document.getElementById('employeeModal');
    const detailModal = document.getElementById('detailModal');
    
    document.getElementById('addProductBtn').addEventListener('click', () => {
        editingProductId = null;
        document.getElementById('productModalTitle').textContent = 'Yangi mahsulot';
        document.getElementById('productForm').reset();
        productModal.classList.add('active');
    });
    
    document.getElementById('addEmployeeBtn').addEventListener('click', () => {
        editingEmployeeId = null;
        document.getElementById('employeeModalTitle').textContent = 'Yangi ishchi';
        document.getElementById('employeeForm').reset();
        employeeModal.classList.add('active');
    });
    
    document.getElementById('closeProductModal').addEventListener('click', () => {
        productModal.classList.remove('active');
    });
    
    document.getElementById('cancelProductBtn').addEventListener('click', () => {
        productModal.classList.remove('active');
    });
    
    document.getElementById('closeEmployeeModal').addEventListener('click', () => {
        employeeModal.classList.remove('active');
    });
    
    document.getElementById('cancelEmployeeBtn').addEventListener('click', () => {
        employeeModal.classList.remove('active');
    });
    
    document.getElementById('closeDetailModal').addEventListener('click', () => {
        detailModal.classList.remove('active');
    });
    
    [productModal, employeeModal, detailModal].forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.classList.remove('active');
            }
        });
    });
}

function setupForms() {
    document.getElementById('productForm').addEventListener('submit', (e) => {
        e.preventDefault();
        
        const product = {
            id: editingProductId || Date.now(),
            name: document.getElementById('productName').value,
            price: parseInt(document.getElementById('productPrice').value),
            quantity: parseInt(document.getElementById('productQuantity').value),
            category: document.getElementById('productCategory').value,
            description: document.getElementById('productDescription').value
        };
        
        if (editingProductId) {
            const index = products.findIndex(p => p.id === editingProductId);
            products[index] = product;
        } else {
            products.push(product);
        }
        
        renderProducts();
        updateDashboard();
        document.getElementById('productModal').classList.remove('active');
        document.getElementById('productForm').reset();
    });
    
    document.getElementById('employeeForm').addEventListener('submit', (e) => {
        e.preventDefault();
        
        const employee = {
            id: editingEmployeeId || Date.now(),
            name: document.getElementById('employeeName').value,
            phone: document.getElementById('employeePhone').value,
            position: document.getElementById('employeePosition').value,
            salary: parseInt(document.getElementById('employeeSalary').value),
            status: document.getElementById('employeeStatus').value,
            email: document.getElementById('employeeEmail').value
        };
        
        if (editingEmployeeId) {
            const index = employees.findIndex(e => e.id === editingEmployeeId);
            employees[index] = employee;
        } else {
            employees.push(employee);
        }
        
        renderEmployees();
        updateDashboard();
        document.getElementById('employeeModal').classList.remove('active');
        document.getElementById('employeeForm').reset();
    });
    
    document.getElementById('productSearch').addEventListener('input', (e) => {
        renderProducts(e.target.value);
    });
    
    document.getElementById('employeeSearch').addEventListener('input', (e) => {
        renderEmployees(e.target.value);
    });
}

function updateDashboard() {
    document.getElementById('totalProducts').textContent = products.length;
    document.getElementById('availableProducts').textContent = products.filter(p => p.quantity > 0).length;
    document.getElementById('totalEmployees').textContent = employees.length;
    document.getElementById('activeEmployees').textContent = employees.filter(e => e.status === 'active').length;
}

function renderProducts(searchQuery = '') {
    const grid = document.getElementById('productsGrid');
    const filtered = products.filter(p => 
        p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.category.toLowerCase().includes(searchQuery.toLowerCase())
    );
    
    if (filtered.length === 0) {
        grid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 3rem; color: var(--text-secondary);">Mahsulotlar topilmadi</div>';
        return;
    }
    
    grid.innerHTML = filtered.map(product => `
        <div class="item-card">
            <div class="item-card-header">
                <div class="item-title">${product.name}</div>
                <div class="item-subtitle">${product.category}</div>
            </div>
            <div class="item-card-body">
                <div class="item-info">
                    <div class="item-info-row">
                        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M1 1h4l2 9h7l2-7H5"/>
                            <circle cx="6" cy="14" r="1"/>
                            <circle cx="12" cy="14" r="1"/>
                        </svg>
                        <span>Narxi: <strong>${formatPrice(product.price)} so'm</strong></span>
                    </div>
                    <div class="item-info-row">
                        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
                            <rect x="2" y="2" width="12" height="12" rx="2"/>
                            <path d="M2 6h12"/>
                        </svg>
                        <span>Miqdori: <strong>${product.quantity} dona</strong></span>
                    </div>
                    ${product.description ? `<div class="item-info-row" style="color: var(--text-tertiary); font-size: 0.8125rem;">${product.description}</div>` : ''}
                </div>
            </div>
            <div class="item-card-footer">
                <button class="btn btn-secondary btn-sm" onclick="viewProduct(${product.id})">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="8" cy="8" r="3"/>
                        <path d="M1 8s3-5 7-5 7 5 7 5-3 5-7 5-7-5-7-5z"/>
                    </svg>
                    <span>Ko'rish</span>
                </button>
                <button class="btn btn-secondary btn-sm" onclick="editProduct(${product.id})">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M11 2l3 3-9 9H2v-3l9-9z"/>
                    </svg>
                    <span>Tahrirlash</span>
                </button>
                <button class="btn btn-secondary btn-sm btn-icon" onclick="deleteProduct(${product.id})">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M2 4h12M5 4V2h6v2M6 4v8M10 4v8"/>
                    </svg>
                </button>
            </div>
        </div>
    `).join('');
}

function renderEmployees(searchQuery = '') {
    const grid = document.getElementById('employeesGrid');
    const filtered = employees.filter(e => 
        e.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        e.position.toLowerCase().includes(searchQuery.toLowerCase()) ||
        e.phone.includes(searchQuery)
    );
    
    if (filtered.length === 0) {
        grid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 3rem; color: var(--text-secondary);">Ishchilar topilmadi</div>';
        return;
    }
    
    grid.innerHTML = filtered.map(employee => `
        <div class="item-card">
            <div class="item-card-header">
                <div style="display: flex; align-items: center; justify-content: space-between;">
                    <div>
                        <div class="item-title">${employee.name}</div>
                        <div class="item-subtitle">${employee.position}</div>
                    </div>
                    <span class="badge ${employee.status === 'active' ? 'badge-success' : 'badge-danger'}">
                        ${employee.status === 'active' ? 'Faol' : 'Faol emas'}
                    </span>
                </div>
            </div>
            <div class="item-card-body">
                <div class="item-info">
                    <div class="item-info-row">
                        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M2 4h12M6 1v3M10 1v3M2 4v9a2 2 0 002 2h8a2 2 0 002-2V4"/>
                        </svg>
                        <span>${employee.phone}</span>
                    </div>
                    ${employee.email ? `
                    <div class="item-info-row">
                        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
                            <rect x="2" y="4" width="12" height="9" rx="1"/>
                            <path d="M2 4l6 4 6-4"/>
                        </svg>
                        <span>${employee.email}</span>
                    </div>
                    ` : ''}
                    <div class="item-info-row">
                        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
                            <circle cx="8" cy="8" r="7"/>
                            <path d="M8 4v4l3 2"/>
                        </svg>
                        <span>Maosh: <strong>${formatPrice(employee.salary)} so'm</strong></span>
                    </div>
                </div>
            </div>
            <div class="item-card-footer">
                <button class="btn btn-secondary btn-sm" onclick="viewEmployee(${employee.id})">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="8" cy="8" r="3"/>
                        <path d="M1 8s3-5 7-5 7 5 7 5-3 5-7 5-7-5-7-5z"/>
                    </svg>
                    <span>Ko'rish</span>
                </button>
                <button class="btn btn-secondary btn-sm" onclick="editEmployee(${employee.id})">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M11 2l3 3-9 9H2v-3l9-9z"/>
                    </svg>
                    <span>Tahrirlash</span>
                </button>
                <button class="btn btn-secondary btn-sm btn-icon" onclick="deleteEmployee(${employee.id})">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M2 4h12M5 4V2h6v2M6 4v8M10 4v8"/>
                    </svg>
                </button>
            </div>
        </div>
    `).join('');
}

function formatPrice(price) {
    return price.toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");
}

function editProduct(id) {
    const product = products.find(p => p.id === id);
    if (!product) return;
    
    editingProductId = id;
    document.getElementById('productModalTitle').textContent = 'Mahsulotni tahrirlash';
    document.getElementById('productName').value = product.name;
    document.getElementById('productPrice').value = product.price;
    document.getElementById('productQuantity').value = product.quantity;
    document.getElementById('productCategory').value = product.category;
    document.getElementById('productDescription').value = product.description;
    
    document.getElementById('productModal').classList.add('active');
}

function deleteProduct(id) {
    if (confirm('Mahsulotni o\'chirishni xohlaysizmi?')) {
        products = products.filter(p => p.id !== id);
        renderProducts();
        updateDashboard();
    }
}

function viewProduct(id) {
    const product = products.find(p => p.id === id);
    if (!product) return;
    
    const modal = document.getElementById('detailModal');
    document.getElementById('detailModalTitle').textContent = product.name;
    document.getElementById('detailModalContent').innerHTML = `
        <div class="detail-grid">
            <div class="detail-section">
                <h4>Asosiy ma'lumotlar</h4>
                <div class="detail-row">
                    <span class="detail-label">Nomi</span>
                    <span class="detail-value">${product.name}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Kategoriya</span>
                    <span class="detail-value">${product.category}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Narxi</span>
                    <span class="detail-value">${formatPrice(product.price)} so'm</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Miqdori</span>
                    <span class="detail-value">${product.quantity} dona</span>
                </div>
                ${product.description ? `
                <div class="detail-row">
                    <span class="detail-label">Tavsif</span>
                    <span class="detail-value">${product.description}</span>
                </div>
                ` : ''}
            </div>
        </div>
    `;
    modal.classList.add('active');
}

function editEmployee(id) {
    const employee = employees.find(e => e.id === id);
    if (!employee) return;
    
    editingEmployeeId = id;
    document.getElementById('employeeModalTitle').textContent = 'Ishchini tahrirlash';
    document.getElementById('employeeName').value = employee.name;
    document.getElementById('employeePhone').value = employee.phone;
    document.getElementById('employeePosition').value = employee.position;
    document.getElementById('employeeSalary').value = employee.salary;
    document.getElementById('employeeStatus').value = employee.status;
    document.getElementById('employeeEmail').value = employee.email;
    
    document.getElementById('employeeModal').classList.add('active');
}

function deleteEmployee(id) {
    if (confirm('Ishchini o\'chirishni xohlaysizmi?')) {
        employees = employees.filter(e => e.id !== id);
        renderEmployees();
        updateDashboard();
    }
}

function viewEmployee(id) {
    const employee = employees.find(e => e.id === id);
    if (!employee) return;
    
    const modal = document.getElementById('detailModal');
    document.getElementById('detailModalTitle').textContent = employee.name;
    document.getElementById('detailModalContent').innerHTML = `
        <div class="detail-grid">
            <div class="detail-section">
                <h4>Shaxsiy ma'lumotlar</h4>
                <div class="detail-row">
                    <span class="detail-label">Ism Familiya</span>
                    <span class="detail-value">${employee.name}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Telefon</span>
                    <span class="detail-value">${employee.phone}</span>
                </div>
                ${employee.email ? `
                <div class="detail-row">
                    <span class="detail-label">Email</span>
                    <span class="detail-value">${employee.email}</span>
                </div>
                ` : ''}
            </div>
            <div class="detail-section">
                <h4>Ish ma'lumotlari</h4>
                <div class="detail-row">
                    <span class="detail-label">Lavozim</span>
                    <span class="detail-value">${employee.position}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Maosh</span>
                    <span class="detail-value">${formatPrice(employee.salary)} so'm</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Status</span>
                    <span class="detail-value">
                        <span class="badge ${employee.status === 'active' ? 'badge-success' : 'badge-danger'}">
                            ${employee.status === 'active' ? 'Faol' : 'Faol emas'}
                        </span>
                    </span>
                </div>
            </div>
        </div>
    `;
    modal.classList.add('active');
}

document.addEventListener('DOMContentLoaded', initApp);
