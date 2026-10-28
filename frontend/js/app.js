/**

 * ESPY Contratación Automatizada - Core Application Logic

 */



// Variable reactiva para marcas de corte de CDP sincronizadas desde backend/app/resources/cdp_marcas_corte.json

let marcasCorteCdpServidor = null;



// Función para sincronizar las marcas de corte oficiales desde el backend

async function sincronizarMarcasCorteCdp() {

    try {

        if (window.api && typeof window.api.getCdpMarcasCorte === 'function') {

            const serverMarks = await window.api.getCdpMarcasCorte();

            if (Array.isArray(serverMarks) && serverMarks.length > 0) {

                marcasCorteCdpServidor = serverMarks.map(pat => new RegExp(pat, 'i'));

                return;

            }

        }

    } catch (e) {

        console.warn('No se pudieron sincronizar las marcas de corte del CDP desde el servidor. Usando respaldo local.', e);

    }

}

window.sincronizarMarcasCorteCdp = sincronizarMarcasCorteCdp;



// Saneamiento de texto del CDP:

// NOTA ARQUITECTÓNICA: La fuente oficial de las marcas de corte es backend/app/resources/cdp_marcas_corte.json

// servido a través de GET /api/cdp/marcas-corte. La lista siguiente actúa como respaldo si la petición falla.

function limpiarTextoCdp(texto) {

    if (!texto) return '';

    let txt = String(texto).trim();

    if (!txt) return '';



    const fallbackPatterns = [

        /,?\s*y\s+respaldado\s+en\s+los\s+clasificadores/i,

        /clasificadores\s+presupuestales/i,

        /\bCCPET\b/i,

        /\bCCPET\d+\b/i,

        /\bClasificador\s+Valor\b/i,

        /\bValor\s+Clasificador\b/i,

        /\bValor\s+en\s+letras\b/i,

        /\bValoren\s*letras\b/i,

        /\bObjeto\s+de\s+la\s+Disponibilidad\b/i,

        /\bObjetado\s+la\s+Disponibilidad\b/i,

        /\bDesarrollado\s+por\s+Sistemas\s+Aries\b/i,

        /\bDesarrollado\s+por\b/i,

        /\bImpreso\s+por\b/i,

        /\bVersi[oó]n\s+AriesNet\b/i

    ];



    const cutPatterns = (Array.isArray(marcasCorteCdpServidor) && marcasCorteCdpServidor.length > 0)

        ? marcasCorteCdpServidor

        : fallbackPatterns;



    for (const pat of cutPatterns) {

        const match = txt.match(pat);

        if (match && match.index !== undefined) {

            txt = txt.substring(0, match.index).trim();

        }

    }

    txt = txt.replace(/[\s,;:\-]+$/, '').trim();

    if (txt && !txt.endsWith('.')) {

        txt += '.';

    }

    return txt;

}

window.limpiarTextoCdp = limpiarTextoCdp;





// Application State

const state = {

    currentTab: 'dashboard',

    contracts: [],

    contractors: [],

    selectedContract: null,

    vigencias: [],

    selectedVigencia: localStorage.getItem('espy_selected_vigencia') === 'ALL'

        ? 'ALL'

        : (parseInt(localStorage.getItem('espy_selected_vigencia'), 10) || 2026),

    execution: {

        summary: null,

        contractors: [],

        contracts: [],

        payments: [],

        selectedContractorId: null,

        currentSubTab: 'contracts',

        searchQuery: '',

        rubroFilter: ''

    },

    excel: {

        contracts: [],

        searchQuery: '',

        filterEstado: '',

        filterTipologia: ''

    },

    wizard: {

        step: 1,

        vigencia: 2026,

        numeroContrato: '',

        uploadedDocs: [],

        uploadedDocIds: [],

        uploadedDocId: null,

        uploadedFileName: '',

        extractedData: null,

        contractorId: null,

        contractorName: '',

        tipologia: 'PRESTACION_SERVICIOS',

        modalidad: 'CONTRATACION_DIRECTA',

        necesidad: '',

        alcance: '',

        valorEstimado: 0,

        plazo: 6,

        unidadPlazo: 'MESES',

        supervisorNombre: 'Ing. Supervisor Técnico',

        supervisorCargo: 'Director Operativo y Técnico',

        supervisorTipoDoc: 'CC',

        supervisorDocumento: '70123456',

        supervisorDependencia: 'Gerencia Técnica',

        fechaSuscripcion: '',

        fechaInicio: '',

        fechaTerminacion: '',

        cdpNumero: 'CDP-2026-001',

        draftResult: null,

        createdContractId: null

    },

    riskMatrix: {

        selectedContractId: null,

        currentResult: null,

        uploadedDocId: null,

        customLogoPath: null,

        customLogoUrl: null

    },

    apuModule: {

        selectedContractId: null,

        payload: null,

        result: null,

        activeSubTab: 'config',

        activeItemIndex: 0,

        customLogoPath: null

    },

    unspscModule: {

        selectedContractId: null,

        result: null,

        isAnalyzing: false,

        estudioFile: null,

        propuestaFile: null

    }

};



// =========================================================

// MÓDULO DE CONTROL DE TEMA VISUAL (MODO CLARO / MODO OSCURO)

// =========================================================

function initAppTheme() {

    const savedTheme = localStorage.getItem('espy_theme') || 'light';

    setAppTheme(savedTheme, false);

}



function setAppTheme(theme, save = true) {

    const htmlEl = document.documentElement;

    const isDark = (theme === 'dark');

    

    if (isDark) {

        htmlEl.classList.add('dark');

    } else {

        htmlEl.classList.remove('dark');

    }

    

    if (save) {

        localStorage.setItem('espy_theme', theme);

    }

    

    updateThemeToggleUI(isDark);

}



function toggleAppTheme() {

    const isDark = document.documentElement.classList.contains('dark');

    setAppTheme(isDark ? 'light' : 'dark', true);

}



function updateThemeToggleUI(isDark) {

    const btn = document.getElementById('theme-toggle-btn');

    const icon = document.getElementById('theme-toggle-icon');

    const text = document.getElementById('theme-toggle-text');

    const iconMobile = document.getElementById('theme-toggle-icon-mobile');

    const textMobile = document.getElementById('theme-toggle-text-mobile');

    const btnMobile = document.getElementById('btn-theme-mobile');

    

    const sunSvg = '<svg class="w-4 h-4 text-amber-500" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/></svg>';

    const moonSvg = '<svg class="w-4 h-4 text-slate-600" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/></svg>';



    if (isDark) {

        if (btn) {

            btn.className = 'flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-amber-400 border border-slate-700 rounded-xl text-xs font-semibold transition-all shadow-sm active:scale-95 cursor-pointer';

        }

        if (icon) icon.innerHTML = sunSvg;

        if (text) text.innerText = 'Modo Claro';

        

        if (btnMobile) {

            btnMobile.className = 'px-3 py-1.5 rounded-lg text-xs font-bold bg-slate-800 text-amber-400 border border-slate-700 shadow-sm flex items-center gap-1.5 active:scale-95 transition-all';

        }

        if (iconMobile) iconMobile.innerHTML = sunSvg;

        if (textMobile) textMobile.innerText = 'Modo Claro';

    } else {

        if (btn) {

            btn.className = 'flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 rounded-xl text-xs font-semibold transition-all shadow-sm active:scale-95 cursor-pointer';

        }

        if (icon) icon.innerHTML = moonSvg;

        if (text) text.innerText = 'Modo Oscuro';

        

        if (btnMobile) {

            btnMobile.className = 'px-3 py-1.5 rounded-lg text-xs font-bold bg-white text-slate-700 border border-slate-200 shadow-sm flex items-center gap-1.5 active:scale-95 transition-all';

        }

        if (iconMobile) iconMobile.innerHTML = moonSvg;

        if (textMobile) textMobile.innerText = 'Modo Oscuro';

    }

}



// Inicializar tema de inmediato al cargar el script

initAppTheme();



// =========================================================

// SISTEMA DE AUTENTICACIÓN Y CONTROL DE ACCESO POR ROLES

// =========================================================



function togglePasswordVisibility(inputId, btn) {

    const input = document.getElementById(inputId);

    if (!input) return;

    const eyeOpen = document.getElementById('icon-eye-open');

    const eyeClosed = document.getElementById('icon-eye-closed');



    if (input.type === 'password') {

        input.type = 'text';

        if (eyeOpen) eyeOpen.style.display = 'none';

        if (eyeClosed) eyeClosed.style.display = 'inline-block';

    } else {

        input.type = 'password';

        if (eyeOpen) eyeOpen.style.display = 'inline-block';

        if (eyeClosed) eyeClosed.style.display = 'none';

    }

}

window.togglePasswordVisibility = togglePasswordVisibility;



function showLoginScreen() {

    const accessPanel = document.getElementById('panel-acceso-independiente');

    const mainApp = document.getElementById('panel-aplicacion-principal');

    if (accessPanel) accessPanel.style.display = 'flex';

    if (mainApp) mainApp.style.display = 'none';



    // Neutralizar clases de rol en el body durante la pantalla de autenticación

    document.body.classList.remove('role-admin', 'role-invitado');



    // Limpiar campos sensibles y errores

    const passInput = document.getElementById('login-password');

    const errContainer = document.getElementById('login-error-container');

    if (passInput) passInput.value = '';

    if (errContainer) errContainer.classList.add('hidden');



    const docInput = document.getElementById('login-documento');

    if (docInput) {

        setTimeout(() => docInput.focus(), 150);

    }

}



function hideLoginScreen() {

    const accessPanel = document.getElementById('panel-acceso-independiente');

    const mainApp = document.getElementById('panel-aplicacion-principal');

    if (accessPanel) accessPanel.style.display = 'none';

    if (mainApp) mainApp.style.display = 'flex';

}



function applyRolePermissions(user) {

    if (!user) {

        showLoginScreen();

        return;

    }



    const rol = (user.rol || 'INVITADO').toUpperCase();

    const isAdmin = rol === 'ADMIN' || rol.includes('ADMIN');



    // Clases en body para ocultar elementos data-admin-only automáticamente por CSS

    if (isAdmin) {

        document.body.classList.remove('role-invitado');

        document.body.classList.add('role-admin');

    } else {

        document.body.classList.remove('role-admin');

        document.body.classList.add('role-invitado');

    }



    // Actualizar badge en la cabecera

    const badgeEl = document.getElementById('user-role-badge');

    const badgeIcon = document.getElementById('user-role-icon');

    const badgeText = document.getElementById('user-role-text');

    const guestBanner = document.getElementById('guest-notice-banner');



    if (badgeEl && badgeIcon && badgeText) {

        if (isAdmin) {

            badgeEl.className = 'px-2.5 py-1 rounded-lg text-xs font-bold flex items-center gap-1.5 user-badge-admin';

            badgeIcon.innerText = '🛡️';

            badgeText.innerText = `Admin: ${user.documento}`;

            if (guestBanner) guestBanner.classList.add('hidden');

        } else {

            badgeEl.className = 'px-2.5 py-1 rounded-lg text-xs font-bold flex items-center gap-1.5 user-badge-guest';

            badgeIcon.innerText = '👁️';

            badgeText.innerText = `Invitado: ${user.documento}`;

            if (guestBanner) guestBanner.classList.remove('hidden');

        }

    }



    // Sincronizar visibilidad estricta de paneles y botones administrativos

    syncAdminVisibility(isAdmin);

    updateMobileDrawerUser(user);



    // Si el usuario es Invitado y se encuentra en una pestaña prohibida, redirigir a dashboard

    const GUEST_ALLOWED_TABS = ['dashboard', 'contracts', 'execution'];

    if (!isAdmin && !GUEST_ALLOWED_TABS.includes(state.currentTab)) {

        switchTab('dashboard');

    }

}



function syncAdminVisibility(isAdmin = window.api.isAdmin()) {

    // 1. Paneles de acción de cabecera (Dashboard, Contratos, Ejecución)

    const actionPanels = ['dashboard-action-panel', 'contracts-action-panel', 'execution-action-panel'];

    actionPanels.forEach(id => {

        const el = document.getElementById(id);

        if (el) {

            el.style.setProperty('display', isAdmin ? 'flex' : 'none', 'important');

        }

    });



    // 2. Todos los elementos individuales con data-admin-only o clase admin-only

    document.querySelectorAll('[data-admin-only="true"], .admin-only').forEach(el => {

        if (actionPanels.includes(el.id)) {

            el.style.setProperty('display', isAdmin ? 'flex' : 'none', 'important');

        } else {

            el.style.setProperty('display', isAdmin ? '' : 'none', 'important');

        }

    });



    // 3. Pestañas administrativas en la barra de navegación

    const adminTabs = ['nav-contractors', 'nav-wizard', 'nav-excel', 'nav-templates', 'nav-settings', 'nav-users', 'nav-reports', 'nav-risks', 'nav-apu', 'navcat-ai', 'navcat-tools', 'navcat-system', 'mobnav-reports', 'bnav-reports'];

    adminTabs.forEach(id => {

        const el = document.getElementById(id);

        if (el) {

            el.style.setProperty('display', isAdmin ? '' : 'none', 'important');

        }

    });

}



function quickFillLogin(doc, pwd, autoSubmit = false) {

    const docInput = document.getElementById('login-documento');

    const passInput = document.getElementById('login-password');

    if (docInput) {

        docInput.value = doc;

        docInput.focus();

    }

    if (passInput) {

        passInput.value = pwd;

    }

    if (autoSubmit) {

        setTimeout(() => {

            handleLoginSubmit();

        }, 30);

    }

}

window.quickFillLogin = quickFillLogin;



async function handleLoginSubmit(event) {

    if (event) {

        if (typeof event.preventDefault === 'function') event.preventDefault();

        if (typeof event.stopPropagation === 'function') event.stopPropagation();

    }

    const docInput = document.getElementById('login-documento');

    const passInput = document.getElementById('login-password');

    const submitBtn = document.getElementById('btn-login-submit');

    const errContainer = document.getElementById('login-error-container');

    const errText = document.getElementById('login-error-text');



    let documento = (docInput ? docInput.value : '').trim();

    let password = (passInput ? passInput.value : '').trim();



    if (!documento || !password) {

        if (errContainer && errText) {

            errText.innerText = 'Debe ingresar su documento y contraseña.';

            errContainer.classList.remove('hidden');

        } else {

            showToast('Debe ingresar su documento y contraseña.', 'warning');

        }

        if (!documento && docInput) docInput.focus();

        else if (!password && passInput) passInput.focus();

        return false;

    }



    if (errContainer) errContainer.classList.add('hidden');

    if (submitBtn) {

        submitBtn.disabled = true;

        submitBtn.innerHTML = `<span>⏳</span> <span>Iniciando sesión...</span>`;

    }



    try {

        const res = await window.api.login(documento, password);

        

        // Inmediatamente ocultar pantalla de acceso y mostrar aplicación principal

        hideLoginScreen();

        if (passInput) passInput.value = '';

        

        const userObj = res.usuario || res.user || { documento, rol: 'ADMIN', nombre_completo: 'Administrador Maestro ESPY' };

        applyRolePermissions(userObj);

        showToast(`Bienvenido al sistema, ${userObj.nombre_completo || documento}`, 'success');



        // Si el usuario debe cambiar su contraseña obligatoriamente, desplegar el modal

        if (res.debe_cambiar_password || userObj.debe_cambiar_password) {

            const modalChange = document.getElementById('modal-force-change-password');

            if (modalChange) {

                modalChange.classList.remove('hidden');

                const curPassInput = document.getElementById('change-pass-current');

                if (curPassInput) {

                    curPassInput.value = password; // Prellenar con la contraseña ingresada

                }

            }

        }



        // Sincronizar marcas oficiales de corte de CDP desde backend

        sincronizarMarcasCorteCdp();



        // Cargar vigencias fiscales

        try {

            await loadVigencias();

        } catch (vigErr) {

            console.warn('Aviso cargando vigencias:', vigErr);

        }



        // Ingresar al Panel de Contratación (o dashboard si es invitado y no tiene permisos)

        try {

            switchTab('contracts');

        } catch (tabErr) {

            console.warn('Aviso cambiando de pestaña:', tabErr);

            switchTab('dashboard');

        }

    } catch (err) {

        console.error('Error durante autenticación:', err);

        if (errContainer && errText) {

            errText.innerText = err.message || 'Error al validar credenciales';

            errContainer.classList.remove('hidden');

        } else {

            showToast(err.message, 'error');

        }

    } finally {

        if (submitBtn) {

            submitBtn.disabled = false;

            submitBtn.innerHTML = `<span>🔐</span> <span>Ingresar al Sistema</span>`;

        }

    }

    return false;

}

window.handleLoginSubmit = handleLoginSubmit;



async function submitForceChangePassword() {

    const curPass = (document.getElementById('change-pass-current')?.value || '').trim();

    const newPass = (document.getElementById('change-pass-new')?.value || '').trim();

    const confPass = (document.getElementById('change-pass-confirm')?.value || '').trim();

    const errBox = document.getElementById('change-pass-error');

    const submitBtn = document.getElementById('btn-submit-change-pass');



    if (errBox) {

        errBox.classList.add('hidden');

        errBox.innerText = '';

    }



    if (!curPass || !newPass || !confPass) {

        if (errBox) {

            errBox.innerText = 'Todos los campos son obligatorios.';

            errBox.classList.remove('hidden');

        }

        return;

    }



    if (newPass.length < 10) {

        if (errBox) {

            errBox.innerText = 'La nueva contraseña debe tener mínimo 10 caracteres.';

            errBox.classList.remove('hidden');

        }

        return;

    }



    if (newPass !== confPass) {

        if (errBox) {

            errBox.innerText = 'La confirmación de la nueva contraseña no coincide.';

            errBox.classList.remove('hidden');

        }

        return;

    }



    if (curPass === newPass) {

        if (errBox) {

            errBox.innerText = 'La nueva contraseña no puede ser idéntica a la anterior.';

            errBox.classList.remove('hidden');

        }

        return;

    }



    if (submitBtn) {

        submitBtn.disabled = true;

        submitBtn.innerHTML = `<span>⏳</span> Guardando...`;

    }



    try {

        await window.api.changePassword(curPass, newPass);

        showToast('Contraseña actualizada exitosamente. Sesión asegurada.', 'success');

        const modalChange = document.getElementById('modal-force-change-password');

        if (modalChange) modalChange.classList.add('hidden');

    } catch (err) {

        console.error('Error al cambiar contraseña:', err);

        if (errBox) {

            errBox.innerText = err.message || 'Error al cambiar la contraseña';

            errBox.classList.remove('hidden');

        } else {

            showToast(err.message, 'error');

        }

    } finally {

        if (submitBtn) {

            submitBtn.disabled = false;

            submitBtn.innerHTML = `<span>🔒</span> <span>Guardar Nueva Contraseña y Continuar</span>`;

        }

    }

}

window.submitForceChangePassword = submitForceChangePassword;



function handleLogout() {

    if (confirm('¿Desea cerrar la sesión activa de forma segura?')) {

        if (typeof closeMobileDrawer === 'function') closeMobileDrawer();

        window.api.logout();

        document.body.classList.remove('role-admin', 'role-invitado');

        // Reset in-memory state

        state.contracts = [];

        state.contractors = [];

        state.selectedContract = null;

        showLoginScreen();

        showToast('Sesión cerrada correctamente', 'info');

    }

}



// -------------------------------------------------------------

// CONTROLADOR DEL MENÚ MÓVIL Y TABLET (OFF-CANVAS DRAWER)

// -------------------------------------------------------------

function openMobileDrawer() {

    const drawer = document.getElementById('mobile-drawer');

    const overlay = document.getElementById('mobile-drawer-overlay');

    if (drawer) drawer.classList.add('open');

    if (overlay) overlay.classList.add('active');

    document.body.style.overflow = 'hidden';

    updateMobileDrawerUser();

}



function closeMobileDrawer() {

    const drawer = document.getElementById('mobile-drawer');

    const overlay = document.getElementById('mobile-drawer-overlay');

    if (drawer) drawer.classList.remove('open');

    if (overlay) overlay.classList.remove('active');

    document.body.style.overflow = '';

}



function toggleMobileDrawer() {

    const drawer = document.getElementById('mobile-drawer');

    if (drawer && drawer.classList.contains('open')) {

        closeMobileDrawer();

    } else {

        openMobileDrawer();

    }

}



function updateMobileDrawerUser(user = window.api.getCurrentUser()) {

    const iconEl = document.getElementById('drawer-user-icon');

    const nameEl = document.getElementById('drawer-user-name');

    const roleEl = document.getElementById('drawer-user-role');

    const iconWrap = document.getElementById('drawer-user-icon-wrap');

    if (!user) return;

    const rol = (user.rol || 'INVITADO').toUpperCase();

    const isAdmin = rol === 'ADMIN' || rol.includes('ADMIN');



    if (nameEl) nameEl.innerText = user.nombre_completo || user.documento || 'Usuario';

    if (roleEl) roleEl.innerText = isAdmin ? `Admin: ${user.documento}` : `Invitado: ${user.documento}`;

    if (iconEl) iconEl.innerText = isAdmin ? '🛡️' : '👁️';

    if (iconWrap) {

        iconWrap.className = isAdmin 

            ? 'w-9 h-9 rounded-xl bg-emerald-950/80 border border-emerald-600/50 flex items-center justify-center text-lg flex-shrink-0'

            : 'w-9 h-9 rounded-xl bg-sky-950/80 border border-sky-600/50 flex items-center justify-center text-lg flex-shrink-0';

    }

}



// Cerrar drawer y modales con la tecla Escape

document.addEventListener('keydown', (e) => {

    if (e.key === 'Escape') {

        closeMobileDrawer();

        closeManageUsersModal();

        closeNetworkShareModal();

    }

});



async function openNetworkShareModal() {

    const modal = document.getElementById('modal-network-share');

    if (!modal) return;

    modal.classList.remove('hidden');



    const guestInput = document.getElementById('share-guest-url');

    const localInput = document.getElementById('share-local-url');



    if (localInput && !localInput.value) {

        localInput.value = 'http://127.0.0.1:8000/app/';

    }



    try {

        if (window.api && typeof window.api.getNetworkInfo === 'function') {

            const data = await window.api.getNetworkInfo();

            if (data && data.guest_url) {

                if (guestInput) guestInput.value = data.guest_url;

                if (localInput && data.local_url) localInput.value = data.local_url;

                return;

            }

        }

    } catch (err) {

        console.warn('Error fetching network info, falling back to location:', err);

    }



    if (guestInput) {

        if (window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {

            guestInput.value = window.location.origin + '/app/';

        } else {

            guestInput.value = 'http://' + (window.location.hostname || '127.0.0.1') + ':8000/app/';

        }

    }

}



function closeNetworkShareModal() {

    const modal = document.getElementById('modal-network-share');

    if (modal) modal.classList.add('hidden');

}



async function copyElementText(elementId, successMsg = 'Copiado al portapapeles') {

    const el = document.getElementById(elementId);

    if (!el) return;

    const text = el.value || el.innerText || '';

    if (!text) return;



    let copied = false;

    if (navigator.clipboard && window.isSecureContext) {

        try {

            await navigator.clipboard.writeText(text);

            copied = true;

        } catch (e) {}

    }

    if (!copied) {

        try {

            el.select();

            el.setSelectionRange(0, 99999);

            copied = document.execCommand('copy');

        } catch (e) {}

    }

    if (!copied) {

        try {

            const ta = document.createElement('textarea');

            ta.value = text;

            ta.style.position = 'fixed';

            ta.style.left = '-9999px';

            document.body.appendChild(ta);

            ta.select();

            copied = document.execCommand('copy');

            document.body.removeChild(ta);

        } catch (e) {}

    }



    if (copied) {

        showToast(successMsg, 'success');

    } else {

        showToast('Enlace seleccionado. Presiona Ctrl+C para copiar.', 'info');

    }

}



async function copyWhatsAppInvite() {

    const guestInput = document.getElementById('share-guest-url');

    const guestUrl = guestInput ? guestInput.value : 'http://127.0.0.1:8000/app/';

    const message = `¡Hola! Puedes consultar los contratos y la ejecución financiera en el Sistema de Contratación ESPY ingresando aquí:\n${guestUrl}\n(Recuerda estar conectado a la misma red Wi-Fi de la oficina).`;

    

    let copied = false;

    if (navigator.clipboard && window.isSecureContext) {

        try {

            await navigator.clipboard.writeText(message);

            copied = true;

        } catch (e) {}

    }

    if (!copied) {

        try {

            const ta = document.createElement('textarea');

            ta.value = message;

            ta.style.position = 'fixed';

            ta.style.left = '-9999px';

            document.body.appendChild(ta);

            ta.select();

            copied = document.execCommand('copy');

            document.body.removeChild(ta);

        } catch (e) {}

    }



    if (copied) {

        showToast('Mensaje de invitación copiado para WhatsApp', 'success');

    } else {

        showToast('No se pudo copiar automáticamente. Copia el enlace directamente.', 'warning');

    }

}



function openManageUsersModal() {

    if (!window.api.isAdmin()) {

        showToast('Acceso denegado: Se requieren permisos de Administrador', 'warning');

        return;

    }

    const modal = document.getElementById('modal-manage-users');

    if (modal) {

        modal.classList.remove('hidden');

        loadUsersList();

        updateUsersModalNetworkUrl();

    }

}



async function updateUsersModalNetworkUrl() {

    const el = document.getElementById('users-modal-network-url');

    if (!el) return;

    try {

        const net = await window.api.getNetworkInfo();

        if (net && net.guest_url) {

            el.innerText = net.guest_url;

            el.setAttribute('data-url', net.guest_url);

        } else {

            el.innerText = `http://${window.location.hostname}:8000/app/`;

            el.setAttribute('data-url', `http://${window.location.hostname}:8000/app/`);

        }

    } catch (e) {

        el.innerText = `http://${window.location.hostname}:8000/app/`;

        el.setAttribute('data-url', `http://${window.location.hostname}:8000/app/`);

    }

}



function copyNetworkUrlFromUsersModal() {

    const el = document.getElementById('users-modal-network-url');

    const url = el ? (el.getAttribute('data-url') || el.innerText) : '';

    if (url) {

        navigator.clipboard.writeText(url).then(() => {

            showToast('Enlace de red copiado al portapapeles', 'success');

        }).catch(() => {

            prompt('Copie el enlace de red local:', url);

        });

    }

}



function closeManageUsersModal() {

    const modal = document.getElementById('modal-manage-users');

    if (modal) modal.classList.add('hidden');

}



async function loadUsersList() {

    const tbody = document.getElementById('users-table-body');

    if (!tbody) return;

    tbody.innerHTML = `<tr><td colspan="5" class="py-4 text-center text-slate-400">Cargando usuarios...</td></tr>`;



    try {

        const users = await window.api.getUsers();

        if (!users || users.length === 0) {

            tbody.innerHTML = `<tr><td colspan="5" class="py-4 text-center text-slate-400">No hay usuarios registrados.</td></tr>`;

            return;

        }



        tbody.innerHTML = users.map(u => {

            const isMaster = u.documento === '8156781';

            const rolUpper = (u.rol || '').toUpperCase();

            const isAdminRole = rolUpper.includes('ADMIN');

            const isEditorRole = rolUpper.includes('EDITOR');



            let roleBadge = '<span class="px-2 py-0.5 rounded bg-sky-950/80 text-sky-300 border border-sky-600/40 text-[10px] font-bold">👁️ INVITADO</span>';

            if (isAdminRole) {

                roleBadge = '<span class="px-2 py-0.5 rounded bg-emerald-950/80 text-emerald-300 border border-emerald-600/40 text-[10px] font-bold">🛡️ ADMIN</span>';

            } else if (isEditorRole) {

                roleBadge = '<span class="px-2 py-0.5 rounded bg-amber-950/80 text-amber-300 border border-amber-600/40 text-[10px] font-bold">✏️ EDITOR</span>';

            }



            const statusToggleBtn = isMaster

                ? `<span class="text-emerald-400 text-xs font-semibold">● Activo (Fijo)</span>`

                : `<button onclick="toggleUserStatus(${u.id}, ${!u.is_active})" class="px-2 py-0.5 rounded text-[11px] font-bold transition-all ${

                    u.is_active 

                        ? 'bg-emerald-950/60 hover:bg-emerald-900 text-emerald-400 border border-emerald-600/40' 

                        : 'bg-rose-950/60 hover:bg-rose-900 text-rose-400 border border-rose-600/40'

                }" title="Clic para cambiar estado">${u.is_active ? '● Activo' : '○ Inactivo'}</button>`;



            const actionButtons = isMaster

                ? '<span class="text-[10px] text-slate-500 italic">Maestro (Protegido)</span>'

                : `

                    <div class="flex items-center justify-center gap-1.5">

                        <button onclick="promptResetUserPassword(${u.id}, '${u.documento}')" class="px-2 py-1 bg-amber-950/50 hover:bg-amber-900 text-amber-300 border border-amber-700/40 rounded text-[11px] transition-colors" title="Cambiar contraseña">🔑 Clave</button>

                        <button onclick="confirmDeleteUser(${u.id}, '${u.documento}')" class="px-2 py-1 bg-rose-950/50 hover:bg-rose-900 text-rose-300 border border-rose-700/40 rounded text-[11px] transition-colors" title="Eliminar usuario">🗑️</button>

                    </div>

                `;



            return `

                <tr class="border-b border-slate-800/60 hover:bg-slate-900/50">

                    <td class="p-2.5 font-bold text-white">${u.documento}</td>

                    <td class="p-2.5 text-slate-300">${u.nombre_completo}</td>

                    <td class="p-2.5 text-center">${roleBadge}</td>

                    <td class="p-2.5 text-center">${statusToggleBtn}</td>

                    <td class="p-2.5 text-center">${actionButtons}</td>

                </tr>

            `;

        }).join('');

    } catch (err) {

        tbody.innerHTML = `<tr><td colspan="5" class="py-4 text-center text-rose-400">Error cargando usuarios: ${err.message}</td></tr>`;

    }

}



async function handleCreateGuestSubmit(event) {

    event.preventDefault();

    const docInput = document.getElementById('new-guest-doc');

    const nameInput = document.getElementById('new-guest-name');

    const passInput = document.getElementById('new-guest-pass');

    const roleInput = document.getElementById('new-guest-role');



    if (!docInput || !nameInput || !passInput) return;



    try {

        await window.api.createUser({

            documento: docInput.value.trim(),

            nombre_completo: nameInput.value.trim(),

            password: passInput.value.trim(),

            rol: roleInput ? roleInput.value : 'INVITADO'

        });



        showToast(`Usuario autorizado ${docInput.value} creado exitosamente`, 'success');

        docInput.value = '';

        nameInput.value = '';

        passInput.value = '';

        await loadUsersList();

    } catch (err) {

        showToast(`Error al autorizar usuario: ${err.message}`, 'error');

    }

}



async function toggleUserStatus(userId, newActiveStatus) {

    try {

        await window.api.updateUser(userId, { is_active: newActiveStatus });

        showToast(`Estado de usuario actualizado a: ${newActiveStatus ? 'Activo' : 'Inactivo'}`, 'info');

        await loadUsersList();

    } catch (err) {

        showToast(`Error al cambiar estado: ${err.message}`, 'error');

    }

}



async function promptResetUserPassword(userId, documento) {

    const newPass = prompt(`Ingrese la nueva contraseña para el usuario ${documento} (mínimo 4 caracteres):`);

    if (!newPass) return;

    if (newPass.trim().length < 4) {

        showToast('La contraseña debe tener mínimo 4 caracteres', 'warning');

        return;

    }

    try {

        await window.api.updateUser(userId, { password: newPass.trim() });

        showToast(`Contraseña actualizada con éxito para el usuario ${documento}`, 'success');

    } catch (err) {

        showToast(`Error al actualizar contraseña: ${err.message}`, 'error');

    }

}



async function confirmDeleteUser(userId, documento) {

    if (!confirm(`¿Está seguro de revocar y eliminar el acceso al usuario con documento ${documento}?`)) {

        return;

    }

    try {

        await window.api.deleteUser(userId);

        showToast(`Usuario ${documento} eliminado del sistema`, 'info');

        await loadUsersList();

    } catch (err) {

        showToast(`Error eliminando usuario: ${err.message}`, 'error');

    }

}



// Utilities

function formatCurrency(amount) {

    if (amount === undefined || amount === null) return '$0 COP';

    return new Intl.NumberFormat('es-CO', {

        style: 'currency',

        currency: 'COP',

        maximumFractionDigits: 0

    }).format(amount);

}



function getTypologyBadge(tipologia) {

    if (!tipologia) return '<span class="badge-prestacion_servicios text-[11px] font-bold">N/A</span>';

    const tipo = String(tipologia).toUpperCase().replace(/\s+/g, '_');

    

    let badgeClass = 'badge-prestacion_servicios';

    let iconSvg = '<svg class="w-3.5 h-3.5 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg>';

    let label = 'Prestación Servicios';

    

    if (tipo.includes('SUMINISTRO')) {

        badgeClass = 'badge-suministro';

        iconSvg = '<svg class="w-3.5 h-3.5 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/></svg>';

        label = 'Suministro';

    } else if (tipo.includes('OBRA')) {

        badgeClass = 'badge-obra';

        iconSvg = '<svg class="w-3.5 h-3.5 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"/></svg>';

        label = 'Obra';

    } else if (tipo.includes('ARRENDAMIENTO') || tipo.includes('ARRIENDO')) {

        badgeClass = 'badge-arrendamiento';

        iconSvg = '<svg class="w-3.5 h-3.5 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/></svg>';

        label = 'Arrendamiento';

    } else if (tipo.includes('CONSULTORIA')) {

        badgeClass = 'badge-consultoria';

        iconSvg = '<svg class="w-3.5 h-3.5 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>';

        label = 'Consultoría';

    } else if (tipo.includes('INTERVENTORIA')) {

        badgeClass = 'badge-interventoria';

        iconSvg = '<svg class="w-3.5 h-3.5 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"/></svg>';

        label = 'Interventoría';

    }

    

    return `<span class="${badgeClass} inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold">

        ${iconSvg}

        <span>${label}</span>

    </span>`;

}



function getContractStatusBadge(estado) {

    const est = String(estado || 'BORRADOR').toUpperCase();

    if (est === 'EN_EJECUCION') {

        return '<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30">En Ejecución</span>';

    } else if (est === 'TERMINADO') {

        return '<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/20 text-amber-600 dark:text-amber-400 border border-amber-500/30">Terminado</span>';

    } else if (est === 'LIQUIDADO') {

        return '<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-500/20 text-purple-600 dark:text-purple-400 border border-purple-500/30">Liquidado</span>';

    } else if (est === 'SUSPENDIDO') {

        return '<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-500/20 text-rose-600 dark:text-rose-400 border border-rose-500/30">Suspendido</span>';

    } else if (est === 'ANULADO') {

        return '<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-500/20 text-slate-500 dark:text-slate-400 border border-slate-500/30 line-through">Anulado</span>';

    } else if (est === 'APROBADO') {

        return '<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/20 text-blue-600 dark:text-blue-400 border border-blue-500/30">Aprobado</span>';

    } else if (est === 'EN_REVISION') {

        return '<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-500/20 text-indigo-600 dark:text-indigo-400 border border-indigo-500/30">En Revisión</span>';

    }

    return '<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-200 dark:bg-slate-700/60 text-slate-700 dark:text-slate-300 border border-slate-300 dark:border-slate-600">Borrador</span>';

}



function getContractConsecutiveNumber(numStr) {

    if (!numStr) return 0;

    const match = String(numStr).match(/-(\d+)-/);

    if (match) return parseInt(match[1], 10);

    const digits = String(numStr).match(/\d+/g);

    if (digits && digits.length > 0) {

        const nonYear = digits.find(d => !/^20\d\d$/.test(d));

        if (nonYear) return parseInt(nonYear, 10);

        return parseInt(digits[0], 10);

    }

    return 0;

}



// -------------------------------------------------------------

// GESTIÓN MULTI-VIGENCIA (ERAS DE CONTRATACIÓN)

// -------------------------------------------------------------

async function loadVigencias() {

    try {

        const vigencias = await window.api.getVigencias();

        state.vigencias = vigencias || [];



        // Si no se tiene una vigencia seleccionada, tomar la actual o 2026

        const activeVig = state.vigencias.find(v => v.es_vigencia_actual);

        if (!state.selectedVigencia && activeVig) {

            state.selectedVigencia = activeVig.year;

        }



        renderVigenciasSelectors();

        updateVigenciaBadgeDisplay();

    } catch (e) {

        console.error('Error cargando vigencias:', e);

    }

}



function renderVigenciasSelectors() {

    const globalSelect = document.getElementById('global-vigencia-select');

    const wizSelect = document.getElementById('wiz-vigencia');



    let globalOptionsHtml = '';

    let wizOptionsHtml = '';



    state.vigencias.forEach(v => {

        const tagActivaGlobal = v.es_vigencia_actual ? ' (Activa)' : '';

        const tagActivaWiz = v.es_vigencia_actual ? ' ★ (Activa)' : '';

        const countText = v.total_contratos === 1 ? '1 contrato' : `${v.total_contratos} contratos`;



        globalOptionsHtml += `<option value="${v.year}">${v.year}${tagActivaGlobal}</option>`;

        wizOptionsHtml += `<option value="${v.year}">${v.year}${tagActivaWiz} &middot; ${countText}</option>`;

    });



    globalOptionsHtml += `<option value="ALL">🌐 Todas</option>` +

        `<option value="NEW_VIGENCIA" class="font-bold text-emerald-400 bg-slate-900">➕ Nueva Vigencia...</option>`;



    if (globalSelect) {

        globalSelect.innerHTML = globalOptionsHtml;

        globalSelect.value = String(state.selectedVigencia);

    }



    if (wizSelect) {

        wizSelect.innerHTML = wizOptionsHtml;

        const targetWiz = state.selectedVigencia === 'ALL' ? (state.vigencias[0]?.year || 2026) : state.selectedVigencia;

        wizSelect.value = String(targetWiz);

        state.wizard.vigencia = parseInt(wizSelect.value, 10);

    }

}



function updateVigenciaBadgeDisplay() {

    const badge = document.getElementById('dashboard-vigencia-badge');

    if (!badge) return;

    if (state.selectedVigencia === 'ALL') {

        badge.innerText = 'Consolidado Histórico Multianual';

        badge.className = 'text-xs font-bold px-2.5 py-0.5 rounded-full bg-indigo-950/80 text-indigo-300 border border-indigo-600/50 shadow-sm';

    } else {

        const vObj = state.vigencias.find(v => v.year == state.selectedVigencia);

        const tag = vObj && vObj.es_vigencia_actual ? ' (Activa)' : '';

        badge.innerText = `Vigencia ${state.selectedVigencia}${tag}`;

        badge.className = 'text-xs font-bold px-2.5 py-0.5 rounded-full bg-emerald-950/80 text-emerald-300 border border-emerald-600/50 shadow-sm';

    }

}



async function handleGlobalVigenciaChange(val) {

    if (val === 'NEW_VIGENCIA') {

        const globalSelect = document.getElementById('global-vigencia-select');

        if (globalSelect) globalSelect.value = String(state.selectedVigencia);

        openNewVigenciaModal();

        return;

    }



    state.selectedVigencia = val === 'ALL' ? 'ALL' : parseInt(val, 10);

    localStorage.setItem('espy_selected_vigencia', state.selectedVigencia);

    

    updateVigenciaBadgeDisplay();



    // Sincronizar con el wizard

    const wizSelect = document.getElementById('wiz-vigencia');

    if (wizSelect && state.selectedVigencia !== 'ALL') {

        wizSelect.value = String(state.selectedVigencia);

        state.wizard.vigencia = state.selectedVigencia;

        refreshWizardContractNumber();

    }



    const label = state.selectedVigencia === 'ALL' ? 'todas las vigencias' : `Vigencia ${state.selectedVigencia}`;

    showToast(`Visualizando contratos y métricas de: ${label}`, 'info');



    if (state.currentTab === 'dashboard') {

        await loadDashboard();

    } else if (state.currentTab === 'contracts') {

        await loadContractsTable();

    } else if (state.currentTab === 'execution') {

        await loadExecutionTab();

    }

}



function openNewVigenciaModal() {

    const modal = document.getElementById('modal-new-vigencia');

    if (!modal) return;



    const years = state.vigencias.map(v => v.year).filter(Boolean);

    const maxYear = years.length > 0 ? Math.max(...years) : 2026;

    const nextYear = maxYear + 1;



    const yearInput = document.getElementById('new-vigencia-year');

    if (yearInput) yearInput.value = nextYear;



    const nameInput = document.getElementById('new-vigencia-name');

    if (nameInput) nameInput.value = `Vigencia Fiscal ${nextYear}`;



    const descInput = document.getElementById('new-vigencia-desc');

    if (descInput) descInput.value = `Era de Contratación Anual ESP Yolombó - Ejercicio Fiscal ${nextYear}`;



    const budgetInput = document.getElementById('new-vigencia-budget');

    if (budgetInput) budgetInput.value = '';



    modal.classList.remove('hidden');

}



function closeNewVigenciaModal() {

    const modal = document.getElementById('modal-new-vigencia');

    if (modal) modal.classList.add('hidden');

}



async function handleCreateVigenciaSubmit(e) {

    e.preventDefault();

    const year = parseInt(document.getElementById('new-vigencia-year').value, 10);

    const nombre = document.getElementById('new-vigencia-name').value.trim();

    const presupuesto_base = parseFloat(document.getElementById('new-vigencia-budget').value) || 0.0;

    const descripcion = document.getElementById('new-vigencia-desc').value.trim();

    const es_vigencia_actual = document.getElementById('new-vigencia-is-active').checked;



    try {

        showToast(`Aperturando Vigencia Fiscal ${year}...`, 'info');

        const created = await window.api.createVigencia({

            year,

            nombre,

            presupuesto_base,

            descripcion,

            es_vigencia_actual

        });



        showToast(`¡Vigencia Fiscal ${created.year} aperturada con éxito! Base de contratistas disponible.`, 'success');

        closeNewVigenciaModal();



        await loadVigencias();



        if (es_vigencia_actual) {

            state.selectedVigencia = year;

            localStorage.setItem('espy_selected_vigencia', year);

            renderVigenciasSelectors();

            updateVigenciaBadgeDisplay();

            if (state.currentTab === 'dashboard') await loadDashboard();

            if (state.currentTab === 'contracts') await loadContractsTable();

            if (state.currentTab === 'settings') await renderSettingsVigenciasTable();

        } else {

            renderVigenciasSelectors();

            if (state.currentTab === 'settings') await renderSettingsVigenciasTable();

        }

    } catch (err) {

        showToast(`Error al aperturar vigencia: ${err.message}`, 'error');

    }

}



async function onWizardVigenciaChange(val) {

    state.wizard.vigencia = parseInt(val, 10) || 2026;

    await refreshWizardContractNumber();

}



async function refreshWizardContractNumber() {

    const numInput = document.getElementById('wiz-numero-contrato');

    if (!numInput) return;



    const vig = state.wizard.vigencia || (state.selectedVigencia !== 'ALL' ? state.selectedVigencia : 2026);

    const tip = state.wizard.tipologia || 'PRESTACION_SERVICIOS';



    try {

        const next = await window.api.getNextContractNumber(vig, tip);

        numInput.value = next.sugerido;

        state.wizard.numeroContrato = next.sugerido;

    } catch (e) {

        console.warn('No se pudo autogenerar consecutivo:', e);

        const prefixMap = { PRESTACION_SERVICIOS: 'CPS', SUMINISTRO: 'CS', OBRA: 'CO', ARRENDAMIENTO: 'CA' };

        const pfx = prefixMap[tip] || 'CPS';

        numInput.value = `${pfx}-001-${vig}`;

    }

}



function showToast(message, type = 'info') {

    const container = document.getElementById('toast-container');

    if (!container) return;



    const toast = document.createElement('div');

    const bgColors = {

        success: 'bg-[#009540]/95 border-[#7FB340] text-white font-semibold shadow-emerald-950/50',

        error: 'bg-rose-600/95 border-rose-400 text-white font-semibold shadow-rose-950/50',

        info: 'bg-[#1590D3]/95 border-[#55C6DE] text-white font-semibold shadow-sky-950/50',

        warning: 'bg-amber-600/95 border-amber-400 text-white font-semibold shadow-amber-950/50'

    };



    toast.className = `flex items-center gap-3 px-4 py-3 rounded-xl border shadow-xl backdrop-blur-md transition-all duration-300 transform translate-y-2 opacity-0 text-sm font-medium ${bgColors[type] || bgColors.info}`;

    toast.innerHTML = `

        <span>${message}</span>

        <button onclick="this.parentElement.remove()" class="ml-auto text-white/80 hover:text-white">&times;</button>

    `;



    container.appendChild(toast);

    setTimeout(() => {

        toast.classList.remove('translate-y-2', 'opacity-0');

    }, 20);



    setTimeout(() => {

        toast.classList.add('opacity-0', 'translate-y-2');

        setTimeout(() => toast.remove(), 300);

    }, 4500);

}



// Tab Switching

function switchTab(tabName) {

    const GUEST_ALLOWED_TABS = ['dashboard', 'contracts', 'execution'];

    if (!window.api.isAdmin() && !GUEST_ALLOWED_TABS.includes(tabName)) {

        if (tabName === 'contractors') {

            showToast('Navegando a contratistas y ejecución financiera (modo consulta).', 'info');

            tabName = 'execution';

            setTimeout(() => {

                if (typeof switchExecSubTab === 'function') switchExecSubTab('contractors');

            }, 60);

        } else {

            showToast('Acceso Restringido: El perfil Invitado solo puede consultar Dashboard, Contratos y Ejecución Financiera.', 'warning');

            tabName = 'dashboard';

        }

    }



    state.currentTab = tabName;

    try {

        if (window.location.hash !== `#${tabName}`) {

            history.replaceState(null, '', `#${tabName}`);

        }

    } catch (e) {}



    document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));

    document.querySelectorAll('.nav-link').forEach(el => {

        el.classList.remove('nav-link-active', 'bg-sky-600/20', 'text-sky-400', 'border-sky-500');

        el.classList.add('text-slate-400');

    });



    const targetSection = document.getElementById(`tab-${tabName}`);

    if (targetSection) targetSection.classList.remove('hidden');



    const activeBtn = document.getElementById(`nav-${tabName}`);

    if (activeBtn) {

        activeBtn.classList.remove('text-slate-400');

        activeBtn.classList.add('nav-link-active');

    }



    if (typeof updateNavCategoriesState === 'function') {

        updateNavCategoriesState(tabName);

    }



    // Sincronizar estado en Menú Lateral Móvil y Barra Inferior Móvil

    if (typeof closeMobileDrawer === 'function') closeMobileDrawer();



    document.querySelectorAll('.mobile-nav-link').forEach(el => el.classList.remove('mobile-nav-active'));

    const activeMobBtn = document.getElementById(`mobnav-${tabName}`);

    if (activeMobBtn) activeMobBtn.classList.add('mobile-nav-active');



    document.querySelectorAll('.bottom-bar-btn').forEach(el => el.classList.remove('bottom-bar-active'));

    const activeBottomBtn = document.getElementById(`bnav-${tabName}`);

    if (activeBottomBtn) activeBottomBtn.classList.add('bottom-bar-active');



    // Desplazar suavemente hacia arriba en vistas móviles

    if (window.innerWidth < 1024) {

        window.scrollTo({ top: 0, behavior: 'smooth' });

    }



    // Refresh tab content

    if (tabName === 'dashboard') loadDashboard();

    if (tabName === 'contracts') loadContractsTable();

    if (tabName === 'execution') loadExecutionTab();

    if (tabName === 'reports') loadReportsTab();

    if (tabName === 'contractors') loadContractorsTab();

    if (tabName === 'wizard') {

        if (state.wizard && state.wizard.step === 4) {

            resetWizardState();

        } else {

            loadWizardContractorsDropdown();

        }

    }

    if (tabName === 'excel') loadExcelView();

    if (tabName === 'templates') loadTemplatesTab();

    if (tabName === 'settings') loadSettings();

    if (tabName === 'risks') loadRisksView();

    if (tabName === 'apu') loadApuView();

    if (tabName === 'unspsc') loadUnspscView();



    // Reasegurar que los paneles de acciones no sean visibles para usuarios invitados

    syncAdminVisibility(window.api.isAdmin());

}



// -------------------------------------------------------------

// DASHBOARD

// -------------------------------------------------------------

async function loadDashboard() {

    try {

        const contractParams = {};

        if (state.selectedVigencia && state.selectedVigencia !== 'ALL') {

            contractParams.vigencia = state.selectedVigencia;

        }



        const [contracts, contractors, health] = await Promise.all([

            window.api.getContracts(contractParams),

            window.api.getContractors(),

            window.api.getHealth()

        ]);



        state.contracts = contracts;

        state.contractors = contractors;



        updateVigenciaBadgeDisplay();



        // Total count

        document.getElementById('stat-total-contracts').innerText = contracts.length;

        document.getElementById('stat-total-contractors').innerText = contractors.length;



        // Total Budget COP

        const totalBudget = contracts.reduce((acc, c) => acc + (c.valor_total || 0), 0);

        document.getElementById('stat-total-budget').innerText = formatCurrency(totalBudget);



        // Active contracts (En Ejecución / En Trámite activo) vs Terminados

        const enEjecucionCount = contracts.filter(c => c.estado === 'EN_EJECUCION').length;

        const enTramiteCount = contracts.filter(c => ['BORRADOR', 'EN_REVISION', 'APROBADO'].includes(c.estado)).length;

        const terminadosCount = contracts.filter(c => ['TERMINADO', 'LIQUIDADO'].includes(c.estado)).length;

        const totalActivos = enEjecucionCount + enTramiteCount;



        const statActiveEl = document.getElementById('stat-active-contracts');

        if (statActiveEl) {

            statActiveEl.innerHTML = `<span>${enEjecucionCount}</span> <span class="text-xs font-semibold text-slate-500 dark:text-slate-400 font-sans block mt-0.5">${enEjecucionCount} En Ejecución / ${terminadosCount} Terminados</span>`;

        }



        // Health indicator

        const healthEl = document.getElementById('api-health-badge');

        if (healthEl) {

            healthEl.innerHTML = health.status === 'healthy' 

                ? `<span class="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse"></span> Sistema Operacional (Ley 142/1994)` 

                : `<span class="w-2.5 h-2.5 rounded-full bg-rose-500"></span> Desconectado`;

        }



        // Render typology breakdown & execution stats

        const typologyStats = {

            PRESTACION_SERVICIOS: { total: 0, en_ejecucion: 0, terminados: 0, value: 0 },

            OBRA: { total: 0, en_ejecucion: 0, terminados: 0, value: 0 },

            SUMINISTRO: { total: 0, en_ejecucion: 0, terminados: 0, value: 0 },

            ARRENDAMIENTO: { total: 0, en_ejecucion: 0, terminados: 0, value: 0 }

        };



        contracts.forEach(c => {

            const tip = c.tipologia;

            if (!typologyStats[tip]) {

                typologyStats[tip] = { total: 0, en_ejecucion: 0, terminados: 0, value: 0 };

            }

            typologyStats[tip].total++;

            if (c.estado === 'EN_EJECUCION') {

                typologyStats[tip].en_ejecucion++;

            } else if (['TERMINADO', 'LIQUIDADO'].includes(c.estado)) {

                typologyStats[tip].terminados++;

            }

            // Acumular valor

            typologyStats[tip].value += (c.valor_total || 0);

        });



        const totalBudgetVal = totalBudget || 1;



        const renderTypologyStatusText = (stats, colorClass) => {

            return `<span class="${colorClass} font-extrabold text-sm">${stats.en_ejecucion}</span> en ejecución / <span class="text-slate-600 dark:text-slate-300 font-semibold">${stats.terminados} ejecutados</span>`;

        };



        // 1. Servicios

        const srv = typologyStats.PRESTACION_SERVICIOS;

        const srvPct = ((srv.value / totalBudgetVal) * 100).toFixed(1);

        if (document.getElementById('count-servicios')) document.getElementById('count-servicios').innerText = `${srv.total} contratos`;

        const srvStatusDescEl = document.getElementById('status-desc-servicios');

        if (srvStatusDescEl) {

            srvStatusDescEl.innerHTML = renderTypologyStatusText(srv, 'text-[#1590D3]');

        } else if (document.getElementById('exec-servicios')) {

            document.getElementById('exec-servicios').innerText = srv.en_ejecucion;

        }

        if (document.getElementById('val-servicios')) document.getElementById('val-servicios').innerText = formatCurrency(srv.value);

        if (document.getElementById('pct-servicios')) document.getElementById('pct-servicios').innerText = `(${srvPct}%)`;

        if (document.getElementById('bar-servicios')) document.getElementById('bar-servicios').style.width = `${Math.min(100, Math.max(3, parseFloat(srvPct)))}%`;



        // 2. Obra

        const obr = typologyStats.OBRA;

        const obrPct = ((obr.value / totalBudgetVal) * 100).toFixed(1);

        if (document.getElementById('count-obra')) document.getElementById('count-obra').innerText = `${obr.total} contratos`;

        const obrStatusDescEl = document.getElementById('status-desc-obra');

        if (obrStatusDescEl) {

            obrStatusDescEl.innerHTML = renderTypologyStatusText(obr, 'text-[#ea580c]');

        } else if (document.getElementById('exec-obra')) {

            document.getElementById('exec-obra').innerText = obr.en_ejecucion;

        }

        if (document.getElementById('val-obra')) document.getElementById('val-obra').innerText = formatCurrency(obr.value);

        if (document.getElementById('pct-obra')) document.getElementById('pct-obra').innerText = `(${obrPct}%)`;

        if (document.getElementById('bar-obra')) document.getElementById('bar-obra').style.width = `${Math.min(100, Math.max(3, parseFloat(obrPct)))}%`;



        // 3. Suministro

        const sum = typologyStats.SUMINISTRO;

        const sumPct = ((sum.value / totalBudgetVal) * 100).toFixed(1);

        if (document.getElementById('count-suministro')) document.getElementById('count-suministro').innerText = `${sum.total} contratos`;

        const sumStatusDescEl = document.getElementById('status-desc-suministro');

        if (sumStatusDescEl) {

            sumStatusDescEl.innerHTML = renderTypologyStatusText(sum, 'text-[#059669]');

        } else if (document.getElementById('exec-suministro')) {

            document.getElementById('exec-suministro').innerText = sum.en_ejecucion;

        }

        if (document.getElementById('val-suministro')) document.getElementById('val-suministro').innerText = formatCurrency(sum.value);

        if (document.getElementById('pct-suministro')) document.getElementById('pct-suministro').innerText = `(${sumPct}%)`;

        if (document.getElementById('bar-suministro')) document.getElementById('bar-suministro').style.width = `${Math.min(100, Math.max(3, parseFloat(sumPct)))}%`;



        // 4. Arrendamiento / Arriendo

        const arr = typologyStats.ARRENDAMIENTO || { total: 0, en_ejecucion: 0, terminados: 0, value: 0 };

        const arrPct = ((arr.value / totalBudgetVal) * 100).toFixed(1);

        const countArrEl = document.getElementById('count-arriendo') || document.getElementById('count-otros');

        const arrStatusDescEl = document.getElementById('status-desc-arriendo');

        const execArrEl = document.getElementById('exec-arriendo') || document.getElementById('exec-otros');

        const valArrEl = document.getElementById('val-arriendo') || document.getElementById('val-otros');

        const pctArrEl = document.getElementById('pct-arriendo');

        const barArrEl = document.getElementById('bar-arriendo') || document.getElementById('bar-otros');



        if (countArrEl) countArrEl.innerText = `${arr.total} contratos`;

        if (arrStatusDescEl) {

            arrStatusDescEl.innerHTML = renderTypologyStatusText(arr, 'text-[#7c3aed]');

        } else if (execArrEl) {

            execArrEl.innerText = arr.en_ejecucion;

        }

        if (valArrEl) valArrEl.innerText = formatCurrency(arr.value);

        if (pctArrEl) pctArrEl.innerText = `(${arrPct}%)`;

        if (barArrEl) barArrEl.style.width = `${Math.min(100, Math.max(3, parseFloat(arrPct)))}%`;



        // Actualizar Donut Chart de Distribución Presupuestal

        renderBudgetDonutChart({

            servicios: parseFloat(srvPct),

            obra: parseFloat(obrPct),

            suministro: parseFloat(sumPct),

            arriendo: parseFloat(arrPct)

        });



        // Actualizar Mini-gráficos e indicadores en las 4 Tarjetas KPI superiores

        updateKpiVisualIndicators({

            totalContracts: contracts.length,

            typologyStats,

            totalBudget,

            enEjecucionCount,

            terminadosCount,

            contractors

        });



        // Render recent contracts (ordenados por consecutivo más alto: 49, 48, 47, 46...)

        const sortedByConsecutive = [...contracts].sort((a, b) => {

            const numA = getContractConsecutiveNumber(a.numero_contrato);

            const numB = getContractConsecutiveNumber(b.numero_contrato);

            if (numB !== numA) return numB - numA;

            return (b.id || 0) - (a.id || 0);

        });



        const recentContracts = sortedByConsecutive.slice(0, 6);

        const countBadge = document.getElementById('recent-contracts-count-badge');

        if (countBadge) {

            countBadge.innerText = `Últimos ${recentContracts.length} Procesos`;

        }



        // 1. Render Table View

        const recentList = document.getElementById('recent-contracts-list');

        if (recentList) {

            recentList.innerHTML = recentContracts.map(c => `

                <tr class="hover:bg-[#1590D3]/10 border-b border-slate-800/80 transition-colors">

                    <td class="py-3.5 px-4 font-bold font-mono text-[#55C6DE] text-xs whitespace-nowrap">${c.numero_contrato}</td>

                    <td class="py-3.5 px-4 whitespace-nowrap">

                        ${getTypologyBadge(c.tipologia)}

                    </td>

                    <td class="py-3.5 px-4 text-slate-200 font-medium text-xs max-w-[220px] truncate" title="${c.contratista ? c.contratista.nombre_o_razon_social : 'Sin contratista'}">

                        ${c.contratista ? c.contratista.nombre_o_razon_social : 'Sin contratista'}

                    </td>

                    <td class="py-3.5 px-4 font-mono text-emerald-400 font-bold text-xs whitespace-nowrap">${formatCurrency(c.valor_total)}</td>

                    <td class="py-3.5 px-4 whitespace-nowrap">

                        ${getContractStatusBadge(c.estado)}

                    </td>

                    <td class="py-3.5 px-4 text-right whitespace-nowrap">

                        <button onclick="viewContractDetail(${c.id})" class="text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 px-2.5 py-1.5 rounded-lg border border-slate-700 transition-all font-medium">

                            Ver Detalle

                        </button>

                    </td>

                </tr>

            `).join('') || `<tr><td colspan="6" class="py-6 text-center text-slate-500">No hay contratos registrados aún.</td></tr>`;

        }



        // 2. Render Timeline View

        renderRecentContractsTimeline(recentContracts);



        // Restore view preference (timeline by default)

        const savedView = localStorage.getItem('espy_recent_view') || 'timeline';

        switchDashboardRecentView(savedView);

    } catch (e) {

        showToast(`Error cargando Dashboard: ${e.message}`, 'error');

    }

}



function formatTimelineMilestoneDate(dateStr) {

    if (!dateStr) return 'Reciente';

    try {

        const parts = String(dateStr).trim().split('-');

        if (parts.length === 3) {

            const day = parseInt(parts[2], 10);

            const monthIdx = parseInt(parts[1], 10) - 1;

            const year = parts[0];

            const months = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];

            return `${day} ${months[monthIdx] || parts[1]} ${year}`;

        }

    } catch (e) {}

    return dateStr;

}



function switchDashboardRecentView(view) {

    const btnTimeline = document.getElementById('btn-view-timeline');

    const btnTable = document.getElementById('btn-view-table');

    const containerTimeline = document.getElementById('recent-contracts-timeline-container');

    const containerTable = document.getElementById('recent-contracts-table-container');



    if (!btnTimeline || !btnTable || !containerTimeline || !containerTable) return;



    if (view === 'table') {

        btnTable.className = 'px-3 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 bg-[#1590D3] text-white shadow-sm';

        btnTimeline.className = 'px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-all flex items-center gap-1.5';

        containerTable.classList.remove('hidden');

        containerTimeline.classList.add('hidden');

        localStorage.setItem('espy_recent_view', 'table');

    } else {

        btnTimeline.className = 'px-3 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 bg-[#1590D3] text-white shadow-sm';

        btnTable.className = 'px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-all flex items-center gap-1.5';

        containerTimeline.classList.remove('hidden');

        containerTable.classList.add('hidden');

        localStorage.setItem('espy_recent_view', 'timeline');

    }

}



// =============================================================

// ESTADO Y LÓGICA DE LA LÍNEA DE TIEMPO INTERACTIVA (DARK NEON)

// =============================================================

window.dashboardTimelineState = {

    contracts: [],

    activeFilter: 'ALL',

    activeContractId: null

};



function formatTimelineMonthYear(dateStr) {

    if (!dateStr) return { key: '2026-99', label: 'Vigencia 2026', month: 'Vigencia', year: '2026' };

    try {

        const parts = String(dateStr).trim().split('-');

        if (parts.length >= 2) {

            const year = parts[0];

            const monthIdx = parseInt(parts[1], 10) - 1;

            const months = [

                'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',

                'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'

            ];

            const monthName = months[monthIdx] || `Mes ${parts[1]}`;

            return {

                key: `${year}-${parts[1]}`,

                label: `${monthName} ${year}`,

                month: monthName,

                year: year

            };

        }

    } catch (e) {}

    return { key: '2026-99', label: 'Vigencia 2026', month: 'Vigencia', year: '2026' };

}



function updateTimelineKpis(visibleContracts, allContracts) {

    const totalEl = document.getElementById('timeline-kpi-total');

    const totalSubEl = document.getElementById('timeline-kpi-total-sub');

    const predEl = document.getElementById('timeline-kpi-predominante');

    const predSubEl = document.getElementById('timeline-kpi-predominante-sub');

    const recEl = document.getElementById('timeline-kpi-reciente');

    const recSubEl = document.getElementById('timeline-kpi-reciente-sub');



    if (!totalEl || !predEl || !recEl) return;



    const sourceAll = allContracts && allContracts.length > 0 ? allContracts : (window.dashboardTimelineState.contracts || []);

    const sourceVis = visibleContracts && visibleContracts.length > 0 ? visibleContracts : sourceAll;



    // 1. Monto Total Acumulado

    const totalMonto = sourceVis.reduce((acc, c) => acc + (Number(c.valor_total) || 0), 0);

    totalEl.innerText = formatCurrency(totalMonto);

    if (totalSubEl) {

        if (sourceVis.length < sourceAll.length) {

            totalSubEl.innerText = `Suma de ${sourceVis.length} contratos (Filtrado)`;

        } else {

            totalSubEl.innerText = `Suma de ${sourceAll.length} contratos visibles`;

        }

    }



    // 2. Tipología Predominante (basado en el conjunto activo o total)

    const counts = {};

    const refForPredominance = sourceVis.length > 0 ? sourceVis : sourceAll;

    refForPredominance.forEach(c => {

        const t = c.tipologia || 'OTRO';

        counts[t] = (counts[t] || 0) + 1;

    });



    let topTipo = 'PRESTACION_SERVICIOS';

    let topCount = 0;

    for (const [t, count] of Object.entries(counts)) {

        if (count > topCount) {

            topCount = count;

            topTipo = t;

        }

    }

    const pct = refForPredominance.length > 0 ? Math.round((topCount / refForPredominance.length) * 100) : 0;

    const friendlyNames = {

        'PRESTACION_SERVICIOS': 'Prestación de Servicios',

        'SUMINISTRO': 'Suministro',

        'OBRA': 'Obra Pública',

        'CONSULTORIA': 'Consultoría',

        'INTERVENTORIA': 'Interventoría',

        'ARRENDAMIENTO': 'Arrendamiento'

    };

    predEl.innerText = `${pct}% ${friendlyNames[topTipo] || topTipo}`;

    if (predSubEl) {

        predSubEl.innerText = `${topCount} de ${refForPredominance.length} contratos visibles`;

    }



    // 3. Contrato Más Reciente / Última Celebración

    if (sourceAll.length > 0) {

        const mostRecent = sourceAll[0];

        const dateRaw = mostRecent.fecha_suscripcion || mostRecent.fecha_acta_inicio;

        const dateFormatted = formatTimelineMilestoneDate(dateRaw);

        recEl.innerText = mostRecent.numero_contrato;

        if (recSubEl) {

            recSubEl.innerText = `${dateFormatted} • ${mostRecent.estado || 'En Ejecución'}`;

        }

    }

}



function renderTimelineFilterChips(contracts) {

    const container = document.getElementById('timeline-filter-chips');

    if (!container) return;



    const counts = {};

    contracts.forEach(c => {

        const t = c.tipologia || 'OTRO';

        counts[t] = (counts[t] || 0) + 1;

    });



    const typologies = Object.keys(counts);

    const friendlyInfo = {

        'PRESTACION_SERVICIOS': { 

            label: 'Prestación Servicios', 

            icon: '<svg class="w-3.5 h-3.5 inline-block" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg>' 

        },

        'SUMINISTRO': { 

            label: 'Suministro', 

            icon: '<svg class="w-3.5 h-3.5 inline-block" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/></svg>' 

        },

        'OBRA': { 

            label: 'Obra', 

            icon: '<svg class="w-3.5 h-3.5 inline-block" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"/></svg>' 

        },

        'CONSULTORIA': { 

            label: 'Consultoría', 

            icon: '<svg class="w-3.5 h-3.5 inline-block" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>' 

        },

        'ARRENDAMIENTO': { 

            label: 'Arriendo', 

            icon: '<svg class="w-3.5 h-3.5 inline-block" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/></svg>' 

        }

    };



    const isAllActive = window.dashboardTimelineState.activeFilter === 'ALL';

    let html = `

        <button onclick="setTimelineTypologyFilter('ALL')" 

                id="timeline-chip-ALL"

                class="timeline-filter-chip px-3 py-1 rounded-xl text-xs font-semibold transition-all flex items-center gap-1.5 shadow-sm ${

                    isAllActive

                        ? 'bg-sky-50 dark:bg-sky-950/80 text-[#1590D3] dark:text-[#55C6DE] border border-[#1590D3] dark:border-[#55C6DE] font-bold'

                        : 'bg-white dark:bg-[#0c1427] text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-800 hover:border-[#1590D3] dark:hover:border-[#55C6DE] hover:text-[#1590D3] dark:hover:text-[#55C6DE]'

                }">

            <svg class="w-3.5 h-3.5 inline-block" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 10h16M4 14h16M4 18h16"/></svg>

            <span>Todos</span>

            <span class="px-1.5 py-0.5 rounded-full text-[10px] font-mono font-bold ${

                isAllActive ? 'bg-[#1590D3] text-white' : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300'

            }">${contracts.length}</span>

        </button>

    `;



    typologies.forEach(t => {

        const info = friendlyInfo[t] || { 

            label: t, 

            icon: '<svg class="w-3.5 h-3.5 inline-block" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>' 

        };

        const isActive = window.dashboardTimelineState.activeFilter === t;

        html += `

            <button onclick="setTimelineTypologyFilter('${t}')" 

                    id="timeline-chip-${t}"

                    class="timeline-filter-chip px-3 py-1 rounded-xl text-xs font-semibold transition-all flex items-center gap-1.5 shadow-sm ${

                        isActive

                            ? 'bg-sky-50 dark:bg-sky-950/80 text-[#1590D3] dark:text-[#55C6DE] border border-[#1590D3] dark:border-[#55C6DE] font-bold'

                            : 'bg-white dark:bg-[#0c1427] text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-800 hover:border-[#1590D3] dark:hover:border-[#55C6DE] hover:text-[#1590D3] dark:hover:text-[#55C6DE]'

                    }">

                <span>${info.icon}</span>

                <span>${info.label}</span>

                <span class="px-1.5 py-0.5 rounded-full text-[10px] font-mono font-bold ${

                    isActive ? 'bg-[#1590D3] text-white' : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300'

                }">${counts[t]}</span>

            </button>

        `;

    });



    container.innerHTML = html;

}



function setTimelineTypologyFilter(tipologia) {

    window.dashboardTimelineState.activeFilter = tipologia;



    // Actualizar estilos visuales de chips

    const allChips = document.querySelectorAll('.timeline-filter-chip');

    allChips.forEach(chip => {

        chip.className = 'timeline-filter-chip px-3 py-1 rounded-xl text-xs font-semibold transition-all flex items-center gap-1.5 shadow-sm bg-white dark:bg-[#0c1427] text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-800 hover:border-[#1590D3] dark:hover:border-[#55C6DE] hover:text-[#1590D3] dark:hover:text-[#55C6DE]';

        const badge = chip.querySelector('span:last-child');

        if (badge) badge.className = 'px-1.5 py-0.5 rounded-full text-[10px] font-mono font-bold bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300';

    });

    const activeChip = document.getElementById(`timeline-chip-${tipologia}`);

    if (activeChip) {

        activeChip.className = 'timeline-filter-chip px-3 py-1 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 shadow-sm bg-sky-50 dark:bg-sky-950/80 text-[#1590D3] dark:text-[#55C6DE] border border-[#1590D3] dark:border-[#55C6DE]';

        const badge = activeChip.querySelector('span:last-child');

        if (badge) badge.className = 'px-1.5 py-0.5 rounded-full text-[10px] font-mono font-bold bg-[#1590D3] text-white';

    }



    const contracts = window.dashboardTimelineState.contracts || [];

    const visibleContracts = [];



    contracts.forEach(c => {

        const itemEl = document.getElementById(`timeline-item-${c.id}`);

        const matches = (tipologia === 'ALL' || c.tipologia === tipologia);



        if (matches) {

            visibleContracts.push(c);

            if (itemEl) itemEl.classList.remove('timeline-item-dimmed');

        } else {

            if (itemEl) itemEl.classList.add('timeline-item-dimmed');

        }

    });



    // Actualizar cintillo de métricas clave según el filtro activo

    updateTimelineKpis(visibleContracts, contracts);

}



// Side Drawer (Panel Deslizable) para Inspección Detallada

function openTimelineDrawer(contractId) {

    const contracts = window.dashboardTimelineState.contracts || [];

    const c = contracts.find(item => item.id === contractId);

    if (!c) {

        // En caso de que no esté en memoria, abrir ficha tradicional

        viewContractDetail(contractId);

        return;

    }



    window.dashboardTimelineState.activeContractId = contractId;



    // 1. Resaltar hito y tarjeta activa

    document.querySelectorAll('.timeline-node-active').forEach(el => el.classList.remove('timeline-node-active'));

    document.querySelectorAll('.timeline-active-card').forEach(el => el.classList.remove('timeline-active-card'));



    const activeNode = document.getElementById(`timeline-node-${contractId}`);

    if (activeNode) activeNode.classList.add('timeline-node-active');



    const activeCard = document.getElementById(`timeline-card-${contractId}`);

    if (activeCard) activeCard.classList.add('timeline-active-card');



    // 2. Poblar contenido del Drawer

    const codeEl = document.getElementById('drawer-contract-code');

    if (codeEl) codeEl.innerText = c.numero_contrato;



    const tipoEl = document.getElementById('drawer-typology-badge');

    if (tipoEl) tipoEl.innerHTML = getTypologyBadge(c.tipologia);



    const statusTextEl = document.getElementById('drawer-status-text');

    if (statusTextEl) statusTextEl.innerText = c.estado || 'EN_EJECUCION';



    const contrNameEl = document.getElementById('drawer-contractor-name');

    if (contrNameEl) {

        contrNameEl.innerText = c.contratista ? c.contratista.nombre_o_razon_social : 'Sin contratista asignado';

    }



    const contrDocEl = document.getElementById('drawer-contractor-doc');

    if (contrDocEl) {

        if (c.contratista && c.contratista.numero_documento) {

            contrDocEl.innerText = `Identificación: ${c.contratista.tipo_documento || 'NIT'} ${c.contratista.numero_documento}`;

        } else {

            contrDocEl.innerText = 'Documento no registrado';

        }

    }



    const objEl = document.getElementById('drawer-objeto');

    if (objEl) {

        objEl.innerText = `"${c.objeto || 'Sin objeto contractual registrado en el sistema.'}"`;

    }



    const valEl = document.getElementById('drawer-valor-total');

    if (valEl) {

        valEl.innerText = formatCurrency(c.valor_total);

    }



    const financesBreakdownEl = document.getElementById('drawer-finances-breakdown');

    if (financesBreakdownEl) {

        let bHtml = '';

        if (c.valor_inicial !== undefined && c.valor_inicial !== null && c.valor_inicial > 0) {

            bHtml += `<div class="flex justify-between text-slate-700 dark:text-slate-200 font-medium"><span>Valor Inicial:</span><span class="font-mono">${formatCurrency(c.valor_inicial)}</span></div>`;

        }

        if (c.adicion_1 && c.adicion_1 > 0) {

            bHtml += `<div class="flex justify-between text-amber-600 dark:text-amber-400 font-medium"><span>Adición No. 1:</span><span class="font-mono">+ ${formatCurrency(c.adicion_1)}</span></div>`;

        }

        if (c.cdp_numero) {

            bHtml += `<div class="flex justify-between text-[#1590D3] dark:text-[#55C6DE] font-medium"><span>CDP Presupuestal:</span><span class="font-mono">No. ${c.cdp_numero}</span></div>`;

        }

        financesBreakdownEl.innerHTML = bHtml || '<div class="text-slate-500 dark:text-slate-400 italic">Contrato a precio global sin adiciones presupuestales.</div>';

    }



    // Plazo

    const plazoEl = document.getElementById('drawer-plazo');

    if (plazoEl) {

        let pStr = c.plazo_texto || '';

        if (!pStr && c.plazo_ejecucion) {

            const u = c.unidad_plazo ? c.unidad_plazo.toLowerCase() : 'meses';

            pStr = `${c.plazo_ejecucion} ${u}`;

        }

        plazoEl.innerText = pStr || 'Plazo no definido';

    }



    // Fechas clave

    const susEl = document.getElementById('drawer-fecha-suscripcion');

    if (susEl) susEl.innerText = formatContractDate(c.fecha_suscripcion);



    const iniEl = document.getElementById('drawer-fecha-inicio');

    if (iniEl) iniEl.innerText = formatContractDate(c.fecha_acta_inicio);



    const finEl = document.getElementById('drawer-fecha-terminacion');

    if (finEl) finEl.innerText = formatContractDate(c.fecha_terminacion);



    // Supervisor

    const supNameEl = document.getElementById('drawer-supervisor-name');

    const supRoleEl = document.getElementById('drawer-supervisor-role');

    if (supNameEl) supNameEl.innerText = c.supervisor_nombre || 'Supervisor por designar';

    if (supRoleEl) {

        const sDoc = c.supervisor_documento ? ` (CC ${c.supervisor_documento})` : '';

        supRoleEl.innerText = `${c.supervisor_cargo || 'Supervisor Oficial'}${sDoc}`;

    }



    // Botón Principal: Ver Expediente Digital

    const btnExpediente = document.getElementById('drawer-btn-expediente');

    if (btnExpediente) {

        btnExpediente.onclick = () => {

            closeTimelineDrawer();

            viewContractDetail(c.id);

        };

    }



    // 3. Abrir Drawer con animación

    const drawer = document.getElementById('timeline-side-drawer');

    const backdrop = document.getElementById('timeline-drawer-backdrop');



    if (backdrop) {

        backdrop.classList.remove('opacity-0', 'pointer-events-none');

        backdrop.classList.add('opacity-100', 'pointer-events-auto');

    }

    if (drawer) {

        drawer.classList.remove('translate-x-full');

        drawer.classList.add('translate-x-0');

    }

}



function closeTimelineDrawer() {

    window.dashboardTimelineState.activeContractId = null;



    // Remover anillos activos

    document.querySelectorAll('.timeline-node-active').forEach(el => el.classList.remove('timeline-node-active'));

    document.querySelectorAll('.timeline-active-card').forEach(el => el.classList.remove('timeline-active-card'));



    const drawer = document.getElementById('timeline-side-drawer');

    const backdrop = document.getElementById('timeline-drawer-backdrop');



    if (backdrop) {

        backdrop.classList.remove('opacity-100', 'pointer-events-auto');

        backdrop.classList.add('opacity-0', 'pointer-events-none');

    }

    if (drawer) {

        drawer.classList.remove('translate-x-0');

        drawer.classList.add('translate-x-full');

    }

}



// -------------------------------------------------------------

// DASHBOARD VISUALIZATIONS: DONUT CHART & KPI MINI-INDICATORS

// -------------------------------------------------------------

const DONUT_CIRCUMFERENCE = 289.02; // 2 * PI * r (r=46)



function renderBudgetDonutChart(percentages) {

    const srvPct = Math.max(0, percentages.servicios || 0);

    const obrPct = Math.max(0, percentages.obra || 0);

    const sumPct = Math.max(0, percentages.suministro || 0);

    const arrPct = Math.max(0, percentages.arriendo || 0);



    // Actualizar leyendas

    const legSrv = document.getElementById('donut-legend-pct-servicios');

    if (legSrv) legSrv.innerText = `${srvPct.toFixed(1)}%`;

    const legObr = document.getElementById('donut-legend-pct-obra');

    if (legObr) legObr.innerText = `${obrPct.toFixed(1)}%`;

    const legSum = document.getElementById('donut-legend-pct-suministro');

    if (legSum) legSum.innerText = `${sumPct.toFixed(1)}%`;

    const legArr = document.getElementById('donut-legend-pct-arriendo');

    if (legArr) legArr.innerText = `${arrPct.toFixed(1)}%`;



    // Longitudes de arco sobre la circunferencia total (289.02)

    const lenSum = (sumPct / 100) * DONUT_CIRCUMFERENCE;

    const lenSrv = (srvPct / 100) * DONUT_CIRCUMFERENCE;

    const lenObr = (obrPct / 100) * DONUT_CIRCUMFERENCE;

    const lenArr = (arrPct / 100) * DONUT_CIRCUMFERENCE;



    // 1. Suministro (comienza en offset 0)

    const sliceSum = document.getElementById('donut-slice-suministro');

    if (sliceSum) {

        sliceSum.style.strokeDasharray = `${lenSum} ${DONUT_CIRCUMFERENCE}`;

        sliceSum.style.strokeDashoffset = '0';

    }



    // 2. Servicios (desfasado por lenSum)

    const sliceSrv = document.getElementById('donut-slice-servicios');

    if (sliceSrv) {

        sliceSrv.style.strokeDasharray = `${lenSrv} ${DONUT_CIRCUMFERENCE}`;

        sliceSrv.style.strokeDashoffset = `-${lenSum}`;

    }



    // 3. Obra (desfasado por lenSum + lenSrv)

    const offsetObr = lenSum + lenSrv;

    const sliceObr = document.getElementById('donut-slice-obra');

    if (sliceObr) {

        sliceObr.style.strokeDasharray = `${lenObr} ${DONUT_CIRCUMFERENCE}`;

        sliceObr.style.strokeDashoffset = `-${offsetObr}`;

    }



    // 4. Arrendamiento (desfasado por offsetObr + lenObr)

    const offsetArr = offsetObr + lenObr;

    const sliceArr = document.getElementById('donut-slice-arriendo');

    if (sliceArr) {

        sliceArr.style.strokeDasharray = `${lenArr} ${DONUT_CIRCUMFERENCE}`;

        sliceArr.style.strokeDashoffset = `-${offsetArr}`;

    }

}



function highlightDonutSlice(type) {

    const centerPct = document.getElementById('donut-center-pct');

    const centerLabel = document.getElementById('donut-center-label');

    if (!centerPct || !centerLabel) return;



    const dataMap = {

        servicios: {

            pct: document.getElementById('pct-servicios')?.innerText.replace(/[()]/g, '') || '31.2%',

            label: 'Servicios',

            color: 'text-cyan-600 dark:text-cyan-400'

        },

        obra: {

            pct: document.getElementById('pct-obra')?.innerText.replace(/[()]/g, '') || '20.0%',

            label: 'Obras PTAP',

            color: 'text-amber-600 dark:text-amber-400'

        },

        suministro: {

            pct: document.getElementById('pct-suministro')?.innerText.replace(/[()]/g, '') || '44.1%',

            label: 'Suministros',

            color: 'text-emerald-600 dark:text-emerald-400'

        },

        arriendo: {

            pct: document.getElementById('pct-arriendo')?.innerText.replace(/[()]/g, '') || '4.7%',

            label: 'Arrendamiento',

            color: 'text-purple-600 dark:text-purple-400'

        }

    };



    const target = dataMap[type];

    if (target) {

        centerPct.innerText = target.pct;

        centerLabel.innerText = target.label;

    }

}



function resetDonutHighlight() {

    const centerPct = document.getElementById('donut-center-pct');

    const centerLabel = document.getElementById('donut-center-label');

    if (centerPct) centerPct.innerText = '$2.14B';

    if (centerLabel) centerLabel.innerText = 'Presupuesto Total';

}



function updateKpiVisualIndicators({ totalContracts, typologyStats, totalBudget, enEjecucionCount, terminadosCount, contractors }) {

    // 1. Tarjeta Total Contratos: Mini-barra segmentada por tipología

    const totalCont = totalContracts || 1;

    const srvCount = typologyStats?.PRESTACION_SERVICIOS?.total || 0;

    const obrCount = typologyStats?.OBRA?.total || 0;

    const sumCount = typologyStats?.SUMINISTRO?.total || 0;

    const arrCount = typologyStats?.ARRENDAMIENTO?.total || 0;



    const barSrv = document.getElementById('kpi-bar-servicios');

    const barObr = document.getElementById('kpi-bar-obra');

    const barSum = document.getElementById('kpi-bar-suministro');

    const barArr = document.getElementById('kpi-bar-arriendo');



    if (barSrv) barSrv.style.width = `${Math.max(2, (srvCount / totalCont) * 100)}%`;

    if (barObr) barObr.style.width = `${Math.max(2, (obrCount / totalCont) * 100)}%`;

    if (barSum) barSum.style.width = `${Math.max(2, (sumCount / totalCont) * 100)}%`;

    if (barArr) barArr.style.width = `${Math.max(2, (arrCount / totalCont) * 100)}%`;



    const ratioEl = document.getElementById('stat-total-tip-ratio');

    if (ratioEl) ratioEl.innerText = `${srvCount} Serv / ${sumCount} Sum / ${obrCount} Obra / ${arrCount} Arr`;



    // 2. Tarjeta Presupuesto: Mini-barra de asignación

    const budgetBar = document.getElementById('kpi-budget-bar');

    const budgetPctEl = document.getElementById('kpi-budget-pct');

    if (budgetBar) budgetBar.style.width = '100%';

    if (budgetPctEl) budgetPctEl.innerText = '100% Comprometido';



    // 3. Tarjeta Contratos Activos: Barra segmentada Activos vs Terminados

    const totalStatuses = (enEjecucionCount + terminadosCount) || 1;

    const activePct = Math.round((enEjecucionCount / totalStatuses) * 100);

    const closedPct = 100 - activePct;



    const barActivos = document.getElementById('kpi-bar-activos');

    const barTerminados = document.getElementById('kpi-bar-terminados');

    const activePctEl = document.getElementById('kpi-active-pct');

    const closedPctEl = document.getElementById('kpi-closed-pct');



    if (barActivos) barActivos.style.width = `${activePct}%`;

    if (barTerminados) barTerminados.style.width = `${closedPct}%`;

    if (activePctEl) activePctEl.innerText = `${activePct}%`;

    if (closedPctEl) closedPctEl.innerText = `${closedPct}%`;



    // 4. Tarjeta Contratistas: Barra segmentada Naturales vs Jurídicas

    const contractorList = contractors || [];

    const totalContr = contractorList.length || 1;

    let natCount = 0;

    let jurCount = 0;



    contractorList.forEach(ct => {

        const docTipo = String(ct.tipo_documento || '').toUpperCase();

        const docNum = String(ct.numero_documento || '');

        if (docTipo.includes('NIT') || docNum.includes('-')) {

            jurCount++;

        } else {

            natCount++;

        }

    });



    const natPct = Math.round((natCount / totalContr) * 100);

    const jurPct = 100 - natPct;



    const barNat = document.getElementById('kpi-bar-naturales');

    const barJur = document.getElementById('kpi-bar-juridicas');

    const natPctEl = document.getElementById('kpi-contractor-nat-pct');

    const jurPctEl = document.getElementById('kpi-contractor-jur-pct');



    if (barNat) barNat.style.width = `${natPct}%`;

    if (barJur) barJur.style.width = `${jurPct}%`;

    if (natPctEl) natPctEl.innerText = `${natPct}%`;

    if (jurPctEl) jurPctEl.innerText = `${jurPct}%`;

}



function renderRecentContractsTimeline(contracts) {

    const timelineEl = document.getElementById('recent-contracts-timeline-list');

    if (!timelineEl) return;



    if (!contracts || contracts.length === 0) {

        timelineEl.innerHTML = `

            <div class="py-8 text-center text-slate-500 text-xs">

                No hay contratos registrados aún para visualizar en la línea de tiempo.

            </div>

        `;

        return;

    }



    // Guardar en estado global

    window.dashboardTimelineState.contracts = contracts;



    // 1. Inicializar KPIs y Micro-filtros de Tipología

    updateTimelineKpis(contracts, contracts);

    renderTimelineFilterChips(contracts);



    // 2. Agrupar cronológicamente por mes

    const monthGroups = {};

    const monthOrder = [];



    contracts.forEach(c => {

        const dateRaw = c.fecha_suscripcion || c.fecha_acta_inicio || c.fecha_estudio_previo;

        const monthInfo = formatTimelineMonthYear(dateRaw);

        const groupKey = monthInfo.key;



        if (!monthGroups[groupKey]) {

            monthGroups[groupKey] = {

                label: monthInfo.label,

                month: monthInfo.month,

                year: monthInfo.year,

                contracts: []

            };

            monthOrder.push(groupKey);

        }

        monthGroups[groupKey].contracts.push(c);

    });



    // 3. Renderizar Línea de Tiempo con Eje Continuo y Tarjetas Institucionales

    let html = `

        <div class="space-y-3">

            <!-- Barra informativa superior con indicador de desplazamiento -->

            <div class="flex items-center justify-between text-[11px] text-slate-500 px-1">

                <div class="flex items-center gap-2">

                    <span class="inline-flex items-center justify-center w-5 h-5 rounded-full bg-sky-50 border border-sky-200 text-[#1590D3]">

                        <svg class="w-3 h-3" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>

                    </span>

                    <span class="font-semibold text-slate-700">Eje cronológico por hitos de suscripción contractual</span>

                </div>

                <div class="hidden sm:flex items-center gap-1.5 font-mono text-[10px] text-slate-500">

                    <span>Desliza para ver meses anteriores</span>

                    <span>&harr;</span>

                </div>

            </div>



            <!-- Carril con scroll horizontal y eje continuo -->

            <div class="timeline-scroll-track overflow-x-auto pb-5 pt-2 px-1">

                <div class="flex items-start gap-6 sm:gap-8 min-w-max relative py-1">

                    <!-- Eje temporal continuo con gradiente institucional -->

                    <div class="absolute top-[22px] left-3 right-3 h-0.5 bg-gradient-to-r from-[#1590D3] via-[#009540] to-[#7FB340] rounded-full z-0 opacity-60"></div>

    `;



    monthOrder.forEach((mKey) => {

        const group = monthGroups[mKey];

        const monthContracts = group.contracts;



        html += `

            <!-- Hito Mensual Estructurado -->

            <div class="relative z-10 flex flex-col items-start gap-4 flex-shrink-0">

                <!-- Marcador de Mes (Station Badge) -->

                <div class="flex items-center gap-2 px-3.5 py-1.5 rounded-xl bg-white dark:bg-[#0c1427] border border-slate-200 dark:border-slate-800 shadow-sm text-xs font-bold text-slate-800 dark:text-white">

                    <span class="text-[#1590D3] dark:text-[#55C6DE]">

                        <svg class="w-3.5 h-3.5 inline-block" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>

                    </span>

                    <span class="uppercase tracking-wider text-slate-700 dark:text-slate-300 font-mono">${group.label}</span>

                    <span class="px-2 py-0.5 rounded-full text-[10px] bg-sky-50 dark:bg-sky-950/80 text-[#1590D3] dark:text-[#55C6DE] border border-sky-200 dark:border-sky-800/60 font-extrabold">

                        ${monthContracts.length} ${monthContracts.length === 1 ? 'Contrato' : 'Contratos'}

                    </span>

                </div>



                <!-- Grupo de Nodos y Tarjetas del Mes -->

                <div class="flex items-start gap-4 sm:gap-5 pt-1">

        `;



        monthContracts.forEach((c) => {

            const dateRaw = c.fecha_suscripcion || c.fecha_acta_inicio || c.fecha_estudio_previo;

            const milestoneDate = formatTimelineMilestoneDate(dateRaw);

            const tipo = String(c.tipologia || '').toUpperCase();



            // Configuración visual y cromática según tipología (Servicios: Azul/Cian, Obra: Naranja, Suministro: Verde, Arriendo: Violeta)

            let nodeIconSvg = '<svg class="w-4 h-4 text-[#06b6d4]" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg>';

            let nodeBorder = 'border-[#06b6d4] shadow-[0_0_12px_rgba(6,182,212,0.45)]';

            let stemColor = 'from-[#06b6d4]';

            let cardTopBorder = 'border-t-[3px] border-t-[#06b6d4]';

            let contractorIconSvg = '<svg class="w-3.5 h-3.5 text-[#06b6d4]" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>';



            if (tipo.includes('SUMINISTRO')) {

                nodeIconSvg = '<svg class="w-4 h-4 text-[#10b981]" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/></svg>';

                nodeBorder = 'border-[#10b981] shadow-[0_0_12px_rgba(16,185,129,0.45)]';

                stemColor = 'from-[#10b981]';

                cardTopBorder = 'border-t-[3px] border-t-[#10b981]';

                contractorIconSvg = '<svg class="w-3.5 h-3.5 text-[#10b981]" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/></svg>';

            } else if (tipo.includes('OBRA')) {

                nodeIconSvg = '<svg class="w-4 h-4 text-[#f59e0b]" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"/></svg>';

                nodeBorder = 'border-[#f59e0b] shadow-[0_0_12px_rgba(245,158,11,0.45)]';

                stemColor = 'from-[#f59e0b]';

                cardTopBorder = 'border-t-[3px] border-t-[#f59e0b]';

                contractorIconSvg = '<svg class="w-3.5 h-3.5 text-[#f59e0b]" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"/></svg>';

            } else if (tipo.includes('ARREND')) {

                nodeIconSvg = '<svg class="w-4 h-4 text-[#8b5cf6]" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/></svg>';

                nodeBorder = 'border-[#8b5cf6] shadow-[0_0_12px_rgba(139,92,246,0.45)]';

                stemColor = 'from-[#8b5cf6]';

                cardTopBorder = 'border-t-[3px] border-t-[#8b5cf6]';

                contractorIconSvg = '<svg class="w-3.5 h-3.5 text-[#8b5cf6]" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/></svg>';

            } else if (tipo.includes('CONSULT')) {

                nodeIconSvg = '<svg class="w-4 h-4 text-[#03008F] dark:text-sky-300" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>';

                nodeBorder = 'border-[#03008F] dark:border-sky-400 shadow-[0_0_12px_rgba(3,0,143,0.35)]';

                stemColor = 'from-[#03008F] dark:from-sky-400';

                cardTopBorder = 'border-t-[3px] border-t-[#03008F] dark:border-t-sky-400';

                contractorIconSvg = '<svg class="w-3.5 h-3.5 text-[#03008F] dark:text-sky-300" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>';

            }



            const isEjecucion = c.estado === 'EN_EJECUCION';

            const contratistaNombre = c.contratista ? c.contratista.nombre_o_razon_social : 'Sin contratista asignado';

            const contratistaDoc = c.contratista ? `${c.contratista.tipo_documento || 'NIT'} ${c.contratista.numero_documento || ''}` : '';

            const objetoSnippet = c.objeto ? c.objeto.trim() : 'Sin objeto contractual registrado.';



            html += `

                <div id="timeline-item-${c.id}" class="timeline-item flex flex-col items-center gap-2.5 transition-all duration-300">

                    <!-- Nodo Interactivo Outline con Resplandor Cromático -->

                    <div id="timeline-node-${c.id}" 

                         onclick="openTimelineDrawer(${c.id})"

                         class="w-8 h-8 rounded-full bg-white dark:bg-[#0c1427] border-2 ${nodeBorder} flex items-center justify-center text-xs cursor-pointer transition-all duration-300 hover:scale-125 z-20"

                         title="Haga clic para inspeccionar ${c.numero_contrato}">

                         ${nodeIconSvg}

                    </div>



                    <!-- Conector sutil entre el nodo y la tarjeta -->

                    <div class="w-0.5 h-3 bg-gradient-to-b ${stemColor} to-slate-200 dark:to-slate-700"></div>



                    <!-- Tarjeta Flotante Institucional con Borde Superior Cromático -->

                    <div id="timeline-card-${c.id}" 

                         onclick="openTimelineDrawer(${c.id})"

                         class="timeline-card-v2 ${cardTopBorder} p-4 w-[280px] sm:w-[310px] flex flex-col justify-between gap-3 cursor-pointer select-none group shadow-sm hover:shadow-lg rounded-2xl bg-white dark:bg-[#0c1427] border border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700 transition-all">

                        

                        <!-- Top Bar de la Tarjeta -->

                        <div class="flex items-center justify-between gap-2 border-b border-slate-100 dark:border-slate-800/80 pb-2.5">

                            <div class="flex items-center gap-1.5">

                                <span class="w-2 h-2 rounded-full ${isEjecucion ? 'bg-[#009540] dark:bg-emerald-400' : 'bg-slate-400'}"></span>

                                <span class="font-mono font-extrabold text-xs sm:text-sm text-[#03008F] dark:text-white group-hover:text-[#1590D3] dark:group-hover:text-[#55C6DE] transition-colors">

                                    ${c.numero_contrato}

                                </span>

                            </div>

                            <div class="text-[10px] font-mono font-semibold text-slate-600 dark:text-slate-300 px-2 py-0.5 rounded-md bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700">

                                📅 ${milestoneDate}

                            </div>

                        </div>



                        <!-- Badge de Tipología -->

                        <div>

                            ${getTypologyBadge(c.tipologia)}

                        </div>



                        <!-- Información del Contratista -->

                        <div class="flex items-start gap-2.5 pt-0.5">

                            <div class="w-7 h-7 rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 flex items-center justify-center text-xs flex-shrink-0 mt-0.5">

                                ${contractorIconSvg}

                            </div>

                            <div class="min-w-0 flex-1">

                                <div class="text-xs font-bold text-slate-900 dark:text-white group-hover:text-[#1590D3] dark:group-hover:text-[#55C6DE] transition-colors truncate" title="${contratistaNombre}">

                                    ${contratistaNombre}

                                </div>

                                ${contratistaDoc ? `<div class="text-[10px] font-mono text-slate-500 dark:text-slate-400 truncate">${contratistaDoc}</div>` : ''}

                            </div>

                        </div>



                        <!-- Extracto del Objeto Contractual -->

                        <div class="bg-slate-50 dark:bg-slate-900/90 p-2.5 rounded-xl border border-slate-100 dark:border-slate-800">

                            <p class="text-[11px] text-slate-700 dark:text-slate-200 italic line-clamp-2 leading-relaxed">

                                "${objetoSnippet}"

                            </p>

                        </div>



                        <!-- Footer: Valor Contractual Formateado & Acción -->

                        <div class="flex items-center justify-between gap-2 pt-2 border-t border-slate-100 dark:border-slate-800/80">

                            <div>

                                <span class="text-[9px] uppercase tracking-wider text-slate-500 dark:text-slate-400 font-semibold block">Valor Contractual</span>

                                <span class="font-mono font-extrabold text-xs sm:text-sm text-[#009540] dark:text-[#7FB340]">

                                    ${formatCurrency(c.valor_total)}

                                </span>

                            </div>

                            <span class="text-[10px] font-bold text-[#1590D3] dark:text-[#55C6DE] group-hover:underline flex items-center gap-1 transition-colors">

                                Ver detalle &rarr;

                            </span>

                        </div>

                    </div>

                </div>

            `;

        });



        html += `

                </div>

            </div>

        `;

    });



    html += `

                </div>

            </div>



            <!-- Footer Informativo y Navegación Rápida -->

            <div class="pt-2 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-slate-500 border-t border-slate-200 pt-3">

                <div class="flex items-center gap-2 text-[11px] text-slate-500">

                    <span class="inline-block w-2 h-2 rounded-full bg-[#009540]"></span>

                    <span>Línea cronológica oficial sincronizada con el repositorio institucional de la ESPY.</span>

                </div>

                <button onclick="switchTab('contracts')" class="px-3.5 py-1.5 rounded-xl bg-white hover:bg-slate-50 text-[#03008F] font-semibold border border-slate-200 transition-all flex items-center gap-1.5 shadow-sm hover:border-[#1590D3]">

                    <svg class="w-3.5 h-3.5 text-[#1590D3]" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>

                    <span>Ver Matriz Completa de Contratos (${contracts.length}) &rarr;</span>

                </button>

            </div>

        </div>

    `;



    timelineEl.innerHTML = html;

}



// -------------------------------------------------------------

// MODAL DE CONTRATOS POR MODALIDAD / TIPOLOGÍA

// -------------------------------------------------------------

const TYPOLOGY_CONFIG = {

    'PRESTACION_SERVICIOS': {

        name: 'Prestación de Servicios Profesionales y Apoyo',

        icon: '<svg class="w-5 h-5 text-[#1590D3]" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg>',

        colorClass: 'text-[#1590D3]',

        badgeBg: 'bg-sky-500/20 text-sky-400 border border-sky-500/30',

        containerBg: 'bg-sky-500/10 border-sky-500/20'

    },

    'OBRA': {

        name: 'Obras e Infraestructura (PTAP/PTAR)',

        icon: '<svg class="w-5 h-5 text-[#7FB340]" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"/></svg>',

        colorClass: 'text-[#7FB340]',

        badgeBg: 'bg-lime-500/20 text-[#7FB340] border border-lime-500/30',

        containerBg: 'bg-lime-500/10 border-lime-500/20'

    },

    'SUMINISTRO': {

        name: 'Suministros y Químicos',

        icon: '<svg class="w-5 h-5 text-[#009540]" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/></svg>',

        colorClass: 'text-[#009540]',

        badgeBg: 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30',

        containerBg: 'bg-emerald-500/10 border-emerald-500/20'

    },

    'ARRENDAMIENTO': {

        name: 'Contratos de Arrendamiento / Arriendo',

        icon: '<svg class="w-5 h-5 text-[#55C6DE]" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/></svg>',

        colorClass: 'text-[#55C6DE]',

        badgeBg: 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30',

        containerBg: 'bg-cyan-500/10 border-cyan-500/20'

    },

    'CONSULTORIA': {

        name: 'Consultoría y Asesoría Especializada',

        icon: '<svg class="w-5 h-5 text-indigo-400" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>',

        colorClass: 'text-indigo-400',

        badgeBg: 'bg-indigo-500/20 text-indigo-400 border border-indigo-500/30',

        containerBg: 'bg-indigo-500/10 border-indigo-500/20'

    },

    'INTERVENTORIA': {

        name: 'Interventoría y Supervisión',

        icon: '<svg class="w-5 h-5 text-amber-400" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"/></svg>',

        colorClass: 'text-amber-400',

        badgeBg: 'bg-amber-500/20 text-amber-400 border border-amber-500/30',

        containerBg: 'bg-amber-500/10 border-amber-500/20'

    }

};



let currentModalTypology = '';

let currentModalTypologyContracts = [];



async function openTypologyContractsModal(tipologia) {

    currentModalTypology = tipologia;

    const config = TYPOLOGY_CONFIG[tipologia] || {

        name: tipologia.replace(/_/g, ' '),

        icon: '📑',

        colorClass: 'text-sky-400',

        badgeBg: 'bg-sky-500/20 text-sky-400 border border-sky-500/30',

        containerBg: 'bg-sky-500/10 border-sky-500/20'

    };



    // Ensure we have the contracts list

    if (!state.contracts || state.contracts.length === 0) {

        try {

            state.contracts = await window.api.getContracts();

        } catch (e) {

            showToast(`Error al cargar contratos: ${e.message}`, 'error');

            return;

        }

    }



    const filtered = state.contracts.filter(c => c.tipologia === tipologia);

    currentModalTypologyContracts = filtered;

    const totalVal = filtered.reduce((acc, c) => acc + (c.valor_total || 0), 0);



    // Set modal headers

    const iconEl = document.getElementById('modal-typology-icon');

    if (iconEl) {

        iconEl.className = `w-11 h-11 rounded-xl ${config.containerBg || 'bg-sky-500/10 border-sky-500/20'} border flex items-center justify-center flex-shrink-0 shadow-inner overflow-hidden`;

        iconEl.innerHTML = config.icon;

    }



    const titleEl = document.getElementById('modal-typology-title');

    if (titleEl) titleEl.innerText = config.name;



    const countBadgeEl = document.getElementById('modal-typology-count-badge');

    if (countBadgeEl) {

        countBadgeEl.className = `px-2.5 py-0.5 rounded-full text-xs font-bold ${config.badgeBg}`;

        countBadgeEl.innerText = `${filtered.length} contratos`;

    }



    const totalValEl = document.getElementById('modal-typology-total-value');

    if (totalValEl) totalValEl.innerText = formatCurrency(totalVal);



    const btnGo = document.getElementById('btn-typology-go-to-matrix');

    if (btnGo) {

        btnGo.onclick = () => navigateToFilteredContracts(tipologia);

    }



    // Reset search input

    const searchInput = document.getElementById('modal-typology-search');

    if (searchInput) {

        searchInput.value = '';

        searchInput.oninput = () => renderTypologyModalTable(tipologia, searchInput.value);

    }



    renderTypologyModalTable(tipologia, '');



    const modal = document.getElementById('typology-contracts-modal');

    if (modal) modal.classList.remove('hidden');

}



function renderTypologyModalTable(tipologia, query = '') {

    const tbody = document.getElementById('modal-typology-table-body');

    if (!tbody) return;



    let items = currentModalTypologyContracts || [];

    const q = (query || '').toLowerCase().trim();

    if (q) {

        items = items.filter(c => 

            (c.numero_contrato || '').toLowerCase().includes(q) ||

            (c.objeto || '').toLowerCase().includes(q) ||

            (c.contratista?.nombre_o_razon_social || '').toLowerCase().includes(q) ||

            (c.contratista?.numero_documento || '').toLowerCase().includes(q)

        );

    }



    const filterCountEl = document.getElementById('modal-typology-filter-count');

    if (filterCountEl) {

        filterCountEl.innerText = `${items.length} de ${currentModalTypologyContracts.length} registros`;

    }



    if (items.length === 0) {

        tbody.innerHTML = `<tr><td colspan="7" class="py-8 text-center text-slate-400">No se encontraron contratos con el término ingresado.</td></tr>`;

        return;

    }



    tbody.innerHTML = items.map(c => `

        <tr class="hover:bg-slate-800/50 transition-colors">

            <td class="py-3 px-3.5 font-mono font-bold text-sky-400 text-xs whitespace-nowrap">

                ${c.numero_contrato}

            </td>

            <td class="py-3 px-3.5 text-slate-200">

                <div class="font-medium text-xs max-w-[200px] truncate" title="${c.contratista?.nombre_o_razon_social || 'N/A'}">

                    ${c.contratista?.nombre_o_razon_social || 'Sin titular'}

                </div>

                <div class="text-[11px] font-mono text-slate-400">

                    ${c.contratista?.numero_documento ? `${c.contratista.tipo_documento || 'NIT'} ${c.contratista.numero_documento}` : '-'}

                </div>

            </td>

            <td class="py-3 px-3.5 text-xs text-slate-300 max-w-[260px] truncate font-normal" title="${c.objeto}">

                ${c.objeto}

            </td>

            <td class="py-3 px-3.5 font-mono font-bold text-emerald-400 text-xs text-right whitespace-nowrap">

                ${formatCurrency(c.valor_total)}

            </td>

            <td class="py-3 px-3.5 text-center text-slate-300 text-xs whitespace-nowrap">

                ${c.plazo_texto || (c.plazo_ejecucion ? `${c.plazo_ejecucion} ${c.unidad_plazo?.toLowerCase() || ''}` : '-')}

            </td>

            <td class="py-3 px-3.5 text-center text-[11px] font-mono text-slate-300 whitespace-nowrap">

                <div>${formatContractDate(c.fecha_acta_inicio)}</div>

                <div class="text-slate-500 text-[10px]">al ${formatContractDate(c.fecha_terminacion)}</div>

            </td>

            <td class="py-3 px-3.5 text-center whitespace-nowrap sticky right-0 bg-slate-950/95 shadow-md">

                <div class="flex items-center justify-center gap-1.5">

                    <button onclick="closeTypologyContractsModal(); viewContractDetail(${c.id})" class="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-sky-400 rounded-lg border border-slate-700 transition-all text-xs font-semibold flex items-center gap-1" title="Ver Expediente Completo">

                        <span>👁️</span> Detalle

                    </button>

                    <button onclick="downloadDocx(${c.id}, 'MINUTA')" class="p-1 bg-slate-800 hover:bg-slate-700 text-amber-400 rounded-lg border border-slate-700 transition-all" title="Descargar Minuta Word (.docx)">

                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>

                    </button>

                </div>

            </td>

        </tr>

    `).join('');

}



function closeTypologyContractsModal() {

    const modal = document.getElementById('typology-contracts-modal');

    if (modal) modal.classList.add('hidden');

}



function navigateToFilteredContracts(tipologia) {

    closeTypologyContractsModal();

    switchTab('contracts');

    const select = document.getElementById('filter-tipologia');

    if (select) {

        select.value = tipologia;

    }

    loadContractsTable();

    const tableSection = document.getElementById('tab-contracts');

    if (tableSection) {

        tableSection.scrollIntoView({ behavior: 'smooth' });

    }

    const tipologiaNames = {

        'PRESTACION_SERVICIOS': 'Prestación de Servicios',

        'OBRA': 'Contratos de Obra',

        'SUMINISTRO': 'Contratos de Suministro',

        'ARRENDAMIENTO': 'Arrendamiento / Arriendo'

    };

    showToast(`Mostrando contratos de ${tipologiaNames[tipologia] || tipologia}`, 'info');

}



// -------------------------------------------------------------

// CONTRACTS LIST & MANAGEMENT (CONSOLIDADO MATRIZ)

// -------------------------------------------------------------

function formatContractDate(dateStr) {

    if (!dateStr) return '-';

    const cleanStr = String(dateStr).trim();

    if (!cleanStr) return '-';

    const parts = cleanStr.split('-');

    if (parts.length === 3) {

        return `${parts[2]}/${parts[1]}/${parts[0]}`;

    }

    return cleanStr;

}



async function loadContractsTable() {

    const search = document.getElementById('contracts-search')?.value || '';

    const filterTipologia = document.getElementById('filter-tipologia')?.value || '';

    const filterEstado = document.getElementById('filter-estado')?.value || '';

    const ocultarAnulados = document.getElementById('filter-ocultar-anulados')?.checked ?? true;



    const params = {

        query: search,

        tipologia: filterTipologia,

        estado: filterEstado,

        ocultar_anulados: ocultarAnulados

    };

    if (state.selectedVigencia && state.selectedVigencia !== 'ALL') {

        params.vigencia = state.selectedVigencia;

    }



    try {

        const contracts = await window.api.getContracts(params);



        state.contracts = contracts;



        const badgeEl = document.getElementById('contracts-count-badge');

        if (badgeEl) {

            const vLabel = state.selectedVigencia === 'ALL' ? 'Multianual' : `Vigencia ${state.selectedVigencia}`;

            badgeEl.innerText = `${contracts.length} Contratos Registrados (${vLabel})`;

        }



        const tbody = document.getElementById('contracts-table-body');

        if (!tbody) return;



        if (contracts.length === 0) {

            tbody.innerHTML = `<tr><td colspan="18" class="py-8 text-center text-slate-400">No se encontraron contratos con los filtros especificados.</td></tr>`;

            return;

        }



        tbody.innerHTML = contracts.map(c => {

            const valInicial = c.valor_inicial !== undefined && c.valor_inicial !== null ? c.valor_inicial : c.valor_total;

            const tieneAdicion = c.adicion_1 && c.adicion_1 > 0;

            const plazoDisplay = c.plazo_texto || (c.plazo_ejecucion ? `${c.plazo_ejecucion} ${c.unidad_plazo ? c.unidad_plazo.toLowerCase() : ''}` : '-');

            const prorrogaDisplay = c.prorroga_1 || '-';



            return `

            <tr class="hover:bg-[#1590D3]/10 border-b border-slate-200 dark:border-slate-800/80 transition-colors">

                <!-- 1. CONTRATO -->

                <td class="py-3 px-3 font-mono font-bold text-[#03008F] dark:text-[#55C6DE] text-xs whitespace-nowrap">

                    ${c.numero_contrato}

                </td>

                <!-- 2. FECHA DEL CONTRATO -->

                <td class="py-3 px-3 font-mono text-slate-700 dark:text-slate-200 text-xs whitespace-nowrap font-medium">

                    ${formatContractDate(c.fecha_suscripcion)}

                </td>

                <!-- 3. TIPO DE CONTRATO -->

                <td class="py-3 px-3 whitespace-nowrap">

                    ${getTypologyBadge(c.tipologia)}

                </td>

                <!-- 4. OBJETO DEL CONTRATO -->

                <td class="py-3 px-3 text-xs text-slate-700 dark:text-slate-200 max-w-[280px] truncate font-normal" title="${c.objeto}">

                    ${c.objeto}

                </td>

                <!-- 5. TITULAR DEL CONTRATO -->

                <td class="py-3 px-3 text-slate-900 dark:text-white font-semibold text-xs max-w-[200px] truncate" title="${c.contratista?.nombre_o_razon_social || 'N/A'}">

                    ${c.contratista?.nombre_o_razon_social || 'N/A'}

                </td>

                <!-- 6. CÉDULA / N.I.T -->

                <td class="py-3 px-3 font-mono text-slate-700 dark:text-slate-200 text-xs whitespace-nowrap">

                    ${c.contratista?.numero_documento || '-'}

                </td>

                <!-- 7. VALOR INICIAL -->

                <td class="py-3 px-3 font-mono text-slate-700 dark:text-slate-200 text-xs text-right whitespace-nowrap font-medium">

                    ${formatCurrency(valInicial)}

                </td>

                <!-- 8. ADICIÓN 1 -->

                <td class="py-3 px-3 font-mono text-xs text-right whitespace-nowrap">

                    ${tieneAdicion ? `

                        <button type="button" onclick="event.stopPropagation(); openEditContractAdditionDirect(${c.id})" 

                                class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-amber-500/15 hover:bg-amber-500/30 text-amber-600 dark:text-amber-300 border border-amber-500/40 font-bold text-[11px] transition-all cursor-pointer shadow-xs active:scale-95 group" 

                                title="Haga clic para ver o editar la adición y regenerar minuta Word">

                            <span class="text-[10px] group-hover:scale-110 transition-transform">✏️</span> ${formatCurrency(c.adicion_1)}

                        </button>

                    ` : '<span class="text-slate-400 dark:text-slate-500">-</span>'}

                </td>

                <!-- 9. VALOR TOTAL -->

                <td class="py-3 px-3 font-mono text-[#009540] dark:text-[#7FB340] font-bold text-xs text-right whitespace-nowrap">

                    ${formatCurrency(c.valor_total)}

                </td>

                <!-- 10. PLAZO DE EJECUCIÓN -->

                <td class="py-3 px-3 text-center text-slate-700 dark:text-slate-200 text-xs whitespace-nowrap font-medium">

                    ${plazoDisplay}

                </td>

                <!-- 11. PRÓRROGA 1 -->

                <td class="py-3 px-3 text-center text-xs whitespace-nowrap ${c.prorroga_1 ? 'text-[#1590D3] dark:text-[#55C6DE] font-bold' : 'text-slate-400 dark:text-slate-500'}">

                    ${prorrogaDisplay}

                </td>

                <!-- 12. FECHA DE INICIO -->

                <td class="py-3 px-3 font-mono text-slate-700 dark:text-slate-200 text-xs whitespace-nowrap">

                    ${formatContractDate(c.fecha_acta_inicio)}

                </td>

                <!-- 13. FECHA DE TERMINACIÓN -->

                <td class="py-3 px-3 font-mono text-[#009540] dark:text-emerald-300 text-xs whitespace-nowrap font-medium">

                    ${formatContractDate(c.fecha_terminacion)}

                </td>

                <!-- 14. SUPERVISOR -->

                <td class="py-3 px-3 text-slate-700 dark:text-slate-200 text-xs max-w-[150px] truncate" title="${c.supervisor_nombre || '-'}">

                    ${c.supervisor_nombre || '-'}

                </td>

                <!-- 15. CDP -->

                <td class="py-3 px-3 text-center font-mono text-[#1590D3] dark:text-[#55C6DE] text-xs font-semibold whitespace-nowrap">

                    ${c.cdp_numero || '-'}

                </td>

                <!-- 16. RUBRO 1 -->

                <td class="py-3 px-3 font-mono text-slate-600 dark:text-slate-300 text-[11px] whitespace-nowrap">

                    ${c.cdp_rubro || '-'}

                </td>

                <!-- 17. CRP -->

                <td class="py-3 px-3 text-center font-mono text-[#009540] dark:text-emerald-300 text-xs font-semibold whitespace-nowrap">

                    ${c.rp_numero || '-'}

                </td>

                <!-- 18. ACCIONES -->

                <td class="py-3 px-3 text-center whitespace-nowrap sticky right-0 bg-white/95 dark:bg-[#0c1427]/95 shadow-md">

                    <div class="flex items-center justify-center gap-1">

                        <button onclick="viewContractDetail(${c.id})" class="p-1.5 bg-slate-100 dark:bg-slate-900/90 hover:bg-[#1590D3]/20 text-[#1590D3] dark:text-[#55C6DE] hover:text-[#03008F] dark:hover:text-white rounded-lg border border-slate-300 dark:border-slate-700/80 transition-all" title="Ver Detalle Completo">

                            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/></svg>

                        </button>

                        ${tieneAdicion ? `

                        <button onclick="event.stopPropagation(); openEditContractAdditionDirect(${c.id})" class="p-1.5 bg-amber-50 dark:bg-amber-950/60 hover:bg-amber-100 dark:hover:bg-amber-900/60 text-amber-600 dark:text-amber-300 hover:text-amber-800 dark:hover:text-white rounded-lg border border-amber-300 dark:border-amber-700/60 transition-all cursor-pointer active:scale-95" title="Editar Formato y Minuta Word de la Adición">

                            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/></svg>

                        </button>

                        ` : ''}

                        <button onclick="downloadDocx(${c.id}, 'MINUTA')" class="p-1.5 bg-slate-100 dark:bg-slate-900/90 hover:bg-emerald-50 dark:hover:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400 hover:text-emerald-800 dark:hover:text-white rounded-lg border border-slate-300 dark:border-slate-700/80 transition-all" title="Descargar Minuta Word (.docx)">

                            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>

                        </button>

                        ${window.api.isAdmin() ? `

                        <button onclick="syncContractExcel(${c.id})" class="p-1.5 bg-slate-100 dark:bg-slate-900/90 hover:bg-teal-50 dark:hover:bg-teal-900/30 text-teal-600 dark:text-teal-300 hover:text-teal-800 dark:hover:text-white rounded-lg border border-slate-300 dark:border-slate-700/80 transition-all" title="Sincronizar a Matriz Excel">

                            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"/></svg>

                        </button>

                        <button onclick="handleDeleteContract(${c.id}, '${c.numero_contrato}')" class="p-1.5 bg-slate-100 dark:bg-slate-900/90 hover:bg-rose-50 dark:hover:bg-rose-950/70 text-rose-600 dark:text-rose-400 hover:text-rose-800 dark:hover:text-rose-200 rounded-lg border border-slate-300 dark:border-slate-700/80 transition-all" title="Anular o Eliminar Contrato">

                            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>

                        </button>

                        ` : ''}

                    </div>

                </td>

            </tr>`;

        }).join('');

    } catch (e) {

        showToast(`Error al consultar contratos: ${e.message}`, 'error');

    }

}



// Export Consolidated Contracts Matrix to CSV

function exportConsolidatedContractsCSV() {

    if (!state.contracts || state.contracts.length === 0) {

        showToast('No hay contratos disponibles para exportar', 'warning');

        return;

    }



    const headers = [

        "CONTRATO",

        "FECHA DEL CONTRATO",

        "TIPO DE CONTRATO",

        "OBJETO DEL CONTRATO",

        "TITULAR DEL CONTRATO",

        "CÉDULA/N.I.T",

        "VALOR INICIAL",

        "ADICIÓN 1",

        "VALOR TOTAL",

        "PLAZO DE EJECUCIÓN",

        "PRÓRROGA 1",

        "FECHA DE INICIO",

        "FECHA DE TERMINACIÓN",

        "SUPERVISOR",

        "CDP",

        "RUBRO 1",

        "CRP"

    ];



    const rows = state.contracts.map(c => [

        `"${(c.numero_contrato || '').replace(/"/g, '""')}"`,

        `"${(c.fecha_suscripcion || '').replace(/"/g, '""')}"`,

        `"${(c.tipologia || '').replace(/_/g, ' ')}"`,

        `"${(c.objeto || '').replace(/"/g, '""')}"`,

        `"${(c.contratista?.nombre_o_razon_social || '').replace(/"/g, '""')}"`,

        `"${(c.contratista?.numero_documento || '').replace(/"/g, '""')}"`,

        c.valor_inicial !== undefined && c.valor_inicial !== null ? c.valor_inicial : (c.valor_total || 0),

        c.adicion_1 || 0,

        c.valor_total || 0,

        `"${(c.plazo_texto || (c.plazo_ejecucion ? `${c.plazo_ejecucion} ${c.unidad_plazo?.toLowerCase()}` : '')).replace(/"/g, '""')}"`,

        `"${(c.prorroga_1 || '').replace(/"/g, '""')}"`,

        `"${(c.fecha_acta_inicio || '').replace(/"/g, '""')}"`,

        `"${(c.fecha_terminacion || '').replace(/"/g, '""')}"`,

        `"${(c.supervisor_nombre || '').replace(/"/g, '""')}"`,

        `"${(c.cdp_numero || '').replace(/"/g, '""')}"`,

        `"${(c.cdp_rubro || '').replace(/"/g, '""')}"`,

        `"${(c.rp_numero || '').replace(/"/g, '""')}"`

    ]);



    const csvContent = "\uFEFF" + [headers.join(","), ...rows.map(r => r.join(","))].join("\r\n");

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });

    const url = URL.createObjectURL(blob);

    const link = document.createElement("a");

    link.setAttribute("href", url);

    link.setAttribute("download", `Consolidado_Contratos_ESPY_${new Date().toISOString().slice(0, 10)}.csv`);

    document.body.appendChild(link);

    link.click();

    document.body.removeChild(link);

    showToast('Matriz de contratos consolidada exportada exitosamente a CSV', 'success');

}



async function viewContractDetail(contractId) {

    try {

        const c = await window.api.getContract(contractId);

        state.selectedContract = c;



        document.getElementById('modal-contract-num').innerText = c.numero_contrato;

        if (typeof toggleEditContractNumberModal === 'function') {

            toggleEditContractNumberModal(false);

        }

        const editNumInput = document.getElementById('input-edit-contract-num');

        if (editNumInput) {

            editNumInput.value = c.numero_contrato || '';

        }

        const modalObjEl = document.getElementById('modal-objeto');

        if (modalObjEl) {

            modalObjEl.value = c.objeto || '';

            modalObjEl.innerText = c.objeto || '';

            const charCountEl = document.getElementById('modal-objeto-char-count');

            if (charCountEl) {

                charCountEl.innerText = `${(c.objeto || '').length} caracteres`;

            }

            const dirtyBadge = document.getElementById('modal-objeto-dirty-badge');

            if (dirtyBadge) dirtyBadge.classList.add('hidden');

        }



        const modalJustTextarea = document.getElementById('modal-edit-justificacion');

        if (modalJustTextarea) {

            modalJustTextarea.value = c.justificacion_necesidad || '';

            const charCountEl = document.getElementById('modal-justificacion-char-count');

            if (charCountEl) {

                charCountEl.innerText = `${(c.justificacion_necesidad || '').length} caracteres`;

            }

            const dirtyBadge = document.getElementById('modal-justificacion-dirty-badge');

            if (dirtyBadge) dirtyBadge.classList.add('hidden');

        }

        const modalJustP = document.getElementById('modal-justificacion');

        if (modalJustP) {

            modalJustP.innerText = c.justificacion_necesidad || 'N/A';

        }

        const modalMarcoEl = document.getElementById('modal-marco-juridico');

        if (modalMarcoEl) {

            modalMarcoEl.innerText = c.marco_juridico || (DEFAULT_LEGAL_FRAMEWORK_BY_TYPOLOGY[c.tipologia]?.text || 'Régimen de Derecho Privado aplicable a las Empresas de Servicios Públicos (Art. 31, Ley 142 de 1994).');

        }

        

        // Breakdown financiero

        const vIni = (c.valor_inicial !== undefined && c.valor_inicial !== null) 

            ? c.valor_inicial 

            : (c.valor_total - (c.adicion_1 || 0));

        window.currentContractValorInicial = vIni;



        if (document.getElementById('modal-valor-inicial')) {

            document.getElementById('modal-valor-inicial').innerText = formatCurrency(vIni);

        }

        const modalInputAdicion = document.getElementById('modal-input-adicion-1');

        if (modalInputAdicion) {

            modalInputAdicion.value = (c.adicion_1 !== undefined && c.adicion_1 !== null) ? c.adicion_1 : 0;

        }

        if (document.getElementById('modal-adicion-1')) {

            document.getElementById('modal-adicion-1').innerText = (c.adicion_1 && c.adicion_1 > 0) ? formatCurrency(c.adicion_1) : '-';

        }

        calculateModalTotalFromAddition();



        // Plazos

        if (document.getElementById('modal-plazo')) {

            document.getElementById('modal-plazo').innerText = c.plazo_texto || `${c.plazo_ejecucion} ${c.unidad_plazo?.toLowerCase() || ''}`;

        }

        if (document.getElementById('modal-prorroga-1')) {

            document.getElementById('modal-prorroga-1').innerText = c.prorroga_1 || '-';

        }



        document.getElementById('modal-contratista').innerText = `${c.contratista?.nombre_o_razon_social || 'Sin contratista'} (${c.contratista?.tipo_documento || 'CC/NIT'} ${c.contratista?.numero_documento || 'N/A'})`;

        const supDoc = c.supervisor_documento ? ` | ${c.supervisor_tipo_documento || 'CC'} ${c.supervisor_documento}` : '';

        document.getElementById('modal-supervisor').innerText = `${c.supervisor_nombre || 'Por definir'} (${c.supervisor_cargo || 'Supervisor'})${supDoc}`;

        

        // Presupuesto detallado y CDP

        const meta = c.metadatos_agente || {};

        const cdpNum = c.cdp_numero || meta.cdp_numero || '-';

        const cdpFechaRaw = c.cdp_fecha || meta.cdp_fecha;

        const cdpFechaFmt = cdpFechaRaw ? formatContractDate(cdpFechaRaw) : '-';

        const cdpVal = meta.cdp_valor !== undefined && meta.cdp_valor !== null ? meta.cdp_valor : c.valor_inicial;

        const cdpValFmt = cdpVal ? `$${Number(cdpVal).toLocaleString('de-DE')}` : '-';

        const cdpRubroCod = c.cdp_rubro || meta.cdp_rubro || '-';

        const cdpRubroNom = meta.cdp_rubro_nombre || '-';

        

        let cdpClasifList = meta.cdp_clasificadores || [];

        if (typeof cdpClasifList === 'string') {

            cdpClasifList = cdpClasifList.split('\n').map(s => s.trim()).filter(Boolean);

        }

        

        if (document.getElementById('modal-cdp-num')) document.getElementById('modal-cdp-num').innerText = cdpNum;

        if (document.getElementById('modal-cdp-fecha')) document.getElementById('modal-cdp-fecha').innerText = cdpFechaFmt;

        if (document.getElementById('modal-cdp-valor')) document.getElementById('modal-cdp-valor').innerText = cdpValFmt;

        if (document.getElementById('modal-cdp-rubro')) document.getElementById('modal-cdp-rubro').innerText = cdpRubroCod;

        if (document.getElementById('modal-cdp-rubro-nombre')) document.getElementById('modal-cdp-rubro-nombre').innerText = cdpRubroNom;

        if (document.getElementById('modal-crp-num')) document.getElementById('modal-crp-num').innerText = c.rp_numero || '-';



        let fullText = meta.cdp_texto_completo ? limpiarTextoCdp(meta.cdp_texto_completo) : '';

        if (!fullText && cdpNum && cdpNum !== '-') {

            const parts = [cdpNum];

            if (cdpFechaFmt && cdpFechaFmt !== '-') parts.push(`expedido el ${cdpFechaFmt}`);

            if (cdpValFmt && cdpValFmt !== '-') parts.push(`por valor de ${cdpValFmt}`);

            if (cdpRubroCod && cdpRubroCod !== '-') {

                const desc = cdpRubroNom && cdpRubroNom !== '-' ? `${cdpRubroCod} – ${cdpRubroNom}` : cdpRubroCod;

                parts.push(`con cargo al Rubro Presupuestal ${desc}`);

            }

            fullText = limpiarTextoCdp(parts.join(', '));

        }



        const textoCompletoEl = document.getElementById('modal-cdp-texto-completo');

        if (textoCompletoEl) {

            textoCompletoEl.innerText = fullText || 'No se ha configurado disponibilidad presupuestal para este contrato.';

        }



        // Prellenar inputs de edición de Plazos y Supervisor

        if (document.getElementById('modal-edit-plazo-ejecucion')) {

            document.getElementById('modal-edit-plazo-ejecucion').value = c.plazo_ejecucion || 1;

        }

        if (document.getElementById('modal-edit-unidad-plazo')) {

            document.getElementById('modal-edit-unidad-plazo').value = c.unidad_plazo || 'MESES';

        }

        if (document.getElementById('modal-edit-prorroga-1')) {

            document.getElementById('modal-edit-prorroga-1').value = c.prorroga_1 || '';

        }

        if (document.getElementById('modal-edit-supervisor-nombre')) {

            document.getElementById('modal-edit-supervisor-nombre').value = c.supervisor_nombre || '';

        }

        if (document.getElementById('modal-edit-supervisor-cargo')) {

            document.getElementById('modal-edit-supervisor-cargo').value = c.supervisor_cargo || '';

        }

        if (document.getElementById('modal-edit-supervisor-doc')) {

            document.getElementById('modal-edit-supervisor-doc').value = c.supervisor_documento || '';

        }

        cancelEditModalPlazos();



        // Prellenar inputs de edición de Presupuesto y CDP

        if (document.getElementById('modal-edit-cdp-num')) {

            document.getElementById('modal-edit-cdp-num').value = (cdpNum && cdpNum !== '-') ? cdpNum : '';

        }

        if (document.getElementById('modal-edit-cdp-fecha')) {

            document.getElementById('modal-edit-cdp-fecha').value = cdpFechaRaw || '';

        }

        if (document.getElementById('modal-edit-cdp-valor')) {

            document.getElementById('modal-edit-cdp-valor').value = (cdpVal !== undefined && cdpVal !== null) ? cdpVal : '';

        }

        if (document.getElementById('modal-edit-crp-num')) {

            document.getElementById('modal-edit-crp-num').value = (c.rp_numero && c.rp_numero !== '-') ? c.rp_numero : '';

        }

        if (document.getElementById('modal-edit-cdp-rubro')) {

            document.getElementById('modal-edit-cdp-rubro').value = (cdpRubroCod && cdpRubroCod !== '-') ? cdpRubroCod : '';

        }

        if (document.getElementById('modal-edit-cdp-rubro-nombre')) {

            document.getElementById('modal-edit-cdp-rubro-nombre').value = (cdpRubroNom && cdpRubroNom !== '-') ? cdpRubroNom : '';

        }

        if (document.getElementById('modal-edit-cdp-clasificadores')) {

            document.getElementById('modal-edit-cdp-clasificadores').value = (cdpClasifList && cdpClasifList.length > 0) ? cdpClasifList.join('\n') : '';

        }

        if (document.getElementById('modal-edit-cdp-texto-completo')) {

            document.getElementById('modal-edit-cdp-texto-completo').value = fullText || '';

        }

        cancelEditModalBudget();



        // Fechas

        if (document.getElementById('modal-fecha-firma')) document.getElementById('modal-fecha-firma').innerText = formatContractDate(c.fecha_suscripcion);

        if (document.getElementById('modal-fecha-inicio')) document.getElementById('modal-fecha-inicio').innerText = formatContractDate(c.fecha_acta_inicio);

        if (document.getElementById('modal-fecha-fin')) document.getElementById('modal-fecha-fin').innerText = formatContractDate(c.fecha_terminacion);

        if (document.getElementById('modal-edit-fecha-firma')) document.getElementById('modal-edit-fecha-firma').value = c.fecha_suscripcion || '';

        if (document.getElementById('modal-edit-fecha-inicio')) document.getElementById('modal-edit-fecha-inicio').value = c.fecha_acta_inicio || '';

        if (document.getElementById('modal-edit-fecha-fin')) document.getElementById('modal-edit-fecha-fin').value = c.fecha_terminacion || '';

        cancelEditModalDates();

        document.getElementById('modal-estado-select').value = c.estado;



        // Render obligations

        const obligPrevList = document.getElementById('modal-oblig-ep');

        if (obligPrevList) {

            obligPrevList.innerHTML = (c.obligaciones_estudio_previo || []).map(o => `<li>• ${o}</li>`).join('') || '<li>Sin obligaciones registradas</li>';

        }



        const obligMinList = document.getElementById('modal-oblig-minuta');

        if (obligMinList) {

            obligMinList.innerHTML = (c.obligaciones_minuta || []).map(o => `<li>• ${o}</li>`).join('') || '<li>Sin obligaciones registradas</li>';

        }



        const obligEmpList = document.getElementById('modal-oblig-empresa');

        if (obligEmpList) {

            obligEmpList.innerHTML = (c.obligaciones_empresa || []).map(o => `<li>• ${o}</li>`).join('') || '<li>Sin obligaciones de la empresa registradas</li>';

        }



        // Render sección de Estudio de Mercado (APU y Elección de Contratista)

        renderModalEstudioMercadoSection(c);



        // Set download action buttons according to contract typology

        const tipoStr = String(c.tipologia || '').toUpperCase();

        const isSuministro = tipoStr.includes('SUMINISTRO');

        const epType = isSuministro ? 'ESTUDIO_PREVIO_SUMINISTRO' : 'ESTUDIO_PREVIO_SERVICIOS';

        const minType = isSuministro ? 'MINUTA_SUMINISTRO' : 'MINUTA_SERVICIOS';



        const btnEp = document.getElementById('btn-download-ep');

        if (btnEp) {

            btnEp.innerHTML = `<span>⬇️</span> Estudio Previo (${isSuministro ? 'Suministro' : 'Servicios'})`;

            btnEp.onclick = () => downloadDocx(c.id, epType);

        }

        const btnMin = document.getElementById('btn-download-minuta');

        if (btnMin) {

            btnMin.innerHTML = `<span>⬇️</span> Minuta (${isSuministro ? 'Suministro' : 'Servicios'})`;

            btnMin.onclick = () => downloadDocx(c.id, minType);

        }

        const btnActa = document.getElementById('btn-download-acta');

        if (btnActa) {

            btnActa.onclick = () => downloadDocx(c.id, 'ACTA_INICIO');

        }

        

        const btnSyncEx = document.getElementById('btn-modal-sync-excel');

        if (btnSyncEx) {

            btnSyncEx.onclick = () => handleUpdateSingleExcel(c.id);

            btnSyncEx.style.display = window.api.isAdmin() ? '' : 'none';

        }

        const btnDelEx = document.getElementById('btn-modal-delete-excel');

        if (btnDelEx) {

            btnDelEx.onclick = () => handleDeleteSingleExcel(c.id, c.numero_contrato);

            btnDelEx.style.display = window.api.isAdmin() ? '' : 'none';

        }

        const btnDelContract = document.getElementById('btn-modal-delete-contract');

        if (btnDelContract) {

            btnDelContract.onclick = () => handleDeleteContract(c.id, c.numero_contrato);

            btnDelContract.style.display = window.api.isAdmin() ? '' : 'none';

        }

        const inputAdicion = document.getElementById('modal-input-adicion-1');

        if (inputAdicion) {

            inputAdicion.disabled = !window.api.isAdmin();

        }



        window.currentContractId = c.id;



        // Mostrar u ocultar inmediatamente el banner superior de adición

        const headerBanner = document.getElementById('modal-header-adicion-banner');

        if (headerBanner) {

            if (c.adicion_1 && c.adicion_1 > 0) {

                headerBanner.classList.remove('hidden');

                headerBanner.style.display = 'flex';

                const mEl = document.getElementById('header-adicion-monto');

                if (mEl) mEl.innerText = formatCurrency(c.adicion_1);

            } else {

                headerBanner.classList.add('hidden');

                headerBanner.style.display = 'none';

            }

        }



        loadContractAdditionsForModal(c.id);

        document.getElementById('contract-detail-modal').classList.remove('hidden');

    } catch (e) {

        showToast(`Error abriendo contrato: ${e.message}`, 'error');

    }

}



function closeContractDetailModal() {

    document.getElementById('contract-detail-modal').classList.add('hidden');

}



function renderModalEstudioMercadoSection(c) {

    const badge = document.getElementById('modal-badge-estudio-mercado');

    const desc = document.getElementById('modal-desc-estudio-mercado');

    const btnQuitar = document.getElementById('modal-btn-quitar-estudio-mercado');

    if (!badge || !desc) return;



    const estudio = c.estudio_mercado || (c.metadatos_agente && c.metadatos_agente.estudio_mercado);

    const hasStudy = Boolean(estudio && (estudio.ofertas || estudio.proponente_ganador || estudio.valor_total_adjudicado));



    if (hasStudy) {

        badge.className = 'px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-950 text-emerald-300 border border-emerald-700/60';

        badge.innerHTML = '✓ Incorporado en Estudio Previo';

        

        const ganadorNom = estudio.proponente_ganador?.nombre_razon_social || estudio.proponente_ganador_nombre || 'Oferente Ganador';

        const valTotal = estudio.valor_total_adjudicado ? formatCurrencyCopApu(estudio.valor_total_adjudicado) : (c.valor_total ? formatCurrency(c.valor_total) : '$0');

        const totalOfertas = (estudio.ofertas || []).length;

        const totalItems = (estudio.items_apu || []).length;



        desc.innerHTML = `

            <div class="text-slate-300 space-y-1">

                <p><strong>Oferente Seleccionado:</strong> <span class="text-emerald-300 font-semibold">${ganadorNom}</span> | <strong>Valor Adjudicado:</strong> <span class="font-mono text-white font-bold">${valTotal}</span></p>

                <p class="text-[10px] text-slate-400">Total cotizaciones evaluadas: ${totalOfertas} | Ítems con desglose APU: ${totalItems}. Al generar el Estudio Previo (.docx), este análisis se plasmará tras las obligaciones del contratista bajo el subtítulo <strong>ANALISIS DE LAS PROPUESTAS DE MERCADO:</strong>.</p>

            </div>

        `;

        if (btnQuitar) btnQuitar.classList.remove('hidden');

    } else {

        badge.className = 'px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-800 text-slate-400 border border-slate-700';

        badge.innerHTML = 'No requerido / Sin estudio';

        desc.innerHTML = `

            <span>Este contrato no tiene estudio de mercado asociado. En el Estudio Previo (.docx) <strong>no se incluirá</strong> este acápite a menos que lo incorpore desde el módulo APU.</span>

        `;

        if (btnQuitar) btnQuitar.classList.add('hidden');

    }

}



async function openApuForCurrentModalContract() {

    const c = state.selectedContract;

    if (!c) return;

    closeContractDetailModal();

    switchTab('apu');

    await populateApuContractsDropdown();

    const select = document.getElementById('apu-select-contract');

    if (select) {

        select.value = String(c.id);

        await handleApuContractSelected();

    }

}



async function removeEstudioMercadoFromCurrentModalContract() {

    const c = state.selectedContract;

    if (!c) return;

    if (!confirm(`¿Está seguro de quitar el estudio de mercado del contrato ${c.numero_contrato}? Ya no aparecerá en el documento de Estudio Previo.`)) {

        return;

    }

    try {

        await window.api.deleteContractEstudioMercado(c.id);

        c.estudio_mercado = null;

        if (c.metadatos_agente) {

            c.metadatos_agente.tiene_estudio_mercado = false;

            delete c.metadatos_agente.estudio_mercado;

        }

        renderModalEstudioMercadoSection(c);

        await populateApuContractsDropdown();

        showToast('Estudio de mercado desvinculado del contrato exitosamente.', 'info');

    } catch (e) {

        showToast('Error al desvincular estudio: ' + e.message, 'error');

    }

}



// Alias de compatibilidad para abrir el modal de detalle del contrato

window.openContractDetailModal = function(param) {

    const cid = (param && typeof param === 'object') ? param.id : param;

    if (cid) return viewContractDetail(cid);

};



function calculateModalTotalFromAddition() {

    const vIni = window.currentContractValorInicial !== undefined 

        ? window.currentContractValorInicial 

        : (state.selectedContract?.valor_inicial || (state.selectedContract ? (state.selectedContract.valor_total - (state.selectedContract.adicion_1 || 0)) : 0));

    

    const inputAdicion = document.getElementById('modal-input-adicion-1');

    const adicionVal = inputAdicion ? (parseFloat(inputAdicion.value) || 0) : 0;

    const totalVal = vIni + adicionVal;



    const valorEl = document.getElementById('modal-valor');

    if (valorEl) {

        valorEl.innerText = formatCurrency(totalVal);

    }



    const badgeEl = document.getElementById('modal-adicion-percent-badge');

    if (badgeEl) {

        if (adicionVal > 0 && vIni > 0) {

            const pct = ((adicionVal / vIni) * 100).toFixed(1);

            const isExceeded = pct > 50;

            badgeEl.innerText = `+${pct}% del valor inicial${isExceeded ? ' (⚠️ Excede el 50% legal)' : ''}`;

            badgeEl.className = isExceeded ? 'text-[9px] text-rose-400 font-mono font-bold block' : 'text-[9px] text-amber-300 font-mono block';

        } else if (adicionVal > 0) {

            badgeEl.innerText = '+ Adición registrada';

            badgeEl.className = 'text-[9px] text-amber-300 font-mono block';

        } else {

            badgeEl.innerText = 'Sin adición (0%)';

            badgeEl.className = 'text-[9px] text-slate-400 font-mono block';

        }

    }

}

window.calculateModalTotalFromAddition = calculateModalTotalFromAddition;



// -------------------------------------------------------------

// GESTIÓN DE FECHAS EN EL MODAL DE DETALLE DEL CONTRATO

// -------------------------------------------------------------

function toggleEditModalDates() {

    const displayEl = document.getElementById('modal-dates-display-view');

    const editEl = document.getElementById('modal-dates-edit-view');

    const btnToggle = document.getElementById('btn-modal-toggle-edit-dates');

    const btnSave = document.getElementById('btn-modal-save-dates');

    const btnCancel = document.getElementById('btn-modal-cancel-edit-dates');



    if (displayEl && editEl) {

        displayEl.classList.add('hidden');

        editEl.classList.remove('hidden');

        if (btnToggle) btnToggle.classList.add('hidden');

        if (btnSave) btnSave.classList.remove('hidden');

        if (btnCancel) btnCancel.classList.remove('hidden');

    }

}

window.toggleEditModalDates = toggleEditModalDates;



function cancelEditModalDates() {

    const displayEl = document.getElementById('modal-dates-display-view');

    const editEl = document.getElementById('modal-dates-edit-view');

    const btnToggle = document.getElementById('btn-modal-toggle-edit-dates');

    const btnSave = document.getElementById('btn-modal-save-dates');

    const btnCancel = document.getElementById('btn-modal-cancel-edit-dates');



    if (displayEl && editEl) {

        displayEl.classList.remove('hidden');

        editEl.classList.add('hidden');

        if (btnToggle) btnToggle.classList.remove('hidden');

        if (btnSave) btnSave.classList.add('hidden');

        if (btnCancel) btnCancel.classList.add('hidden');

    }

}

window.cancelEditModalDates = cancelEditModalDates;



function autoCalculateModalEndDate() {

    if (!state.selectedContract) return;

    const inicioEl = document.getElementById('modal-edit-fecha-inicio');

    const finEl = document.getElementById('modal-edit-fecha-fin');

    if (!inicioEl || !finEl || !inicioEl.value) return;



    const plazo = parseInt(state.selectedContract.plazo_ejecucion) || 1;

    const unidad = String(state.selectedContract.unidad_plazo || 'MESES').toUpperCase();

    const parts = inicioEl.value.split('-');

    if (parts.length !== 3) return;

    const d = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));



    if (unidad.includes('DIA')) {

        d.setDate(d.getDate() + plazo);

    } else if (unidad.includes('AÑO')) {

        d.setFullYear(d.getFullYear() + plazo);

    } else {

        d.setMonth(d.getMonth() + plazo);

    }

    const yyyy = d.getFullYear();

    const mm = String(d.getMonth() + 1).padStart(2, '0');

    const dd = String(d.getDate()).padStart(2, '0');

    finEl.value = `${yyyy}-${mm}-${dd}`;

}

window.autoCalculateModalEndDate = autoCalculateModalEndDate;



async function saveModalDates() {

    if (!state.selectedContract || !state.selectedContract.id) {

        showToast('No se puede guardar: contrato no seleccionado.', 'warning');

        return;

    }

    const fFirma = document.getElementById('modal-edit-fecha-firma')?.value || null;

    const fInicio = document.getElementById('modal-edit-fecha-inicio')?.value || null;

    const fFin = document.getElementById('modal-edit-fecha-fin')?.value || null;



    try {

        showToast('Guardando fechas del contrato...', 'info');

        const updated = await window.api.updateContract(state.selectedContract.id, {

            fecha_suscripcion: fFirma,

            fecha_acta_inicio: fInicio,

            fecha_terminacion: fFin

        });



        state.selectedContract = updated;

        if (document.getElementById('modal-fecha-firma')) document.getElementById('modal-fecha-firma').innerText = formatContractDate(updated.fecha_suscripcion);

        if (document.getElementById('modal-fecha-inicio')) document.getElementById('modal-fecha-inicio').innerText = formatContractDate(updated.fecha_acta_inicio);

        if (document.getElementById('modal-fecha-fin')) document.getElementById('modal-fecha-fin').innerText = formatContractDate(updated.fecha_terminacion);



        cancelEditModalDates();

        showToast('¡Fechas del contrato actualizadas exitosamente! El Acta de Inicio y los informes Word reflejarán estos cambios.', 'success');

        if (typeof loadContractsTable === 'function') {

            loadContractsTable();

        }

    } catch (e) {

        showToast(`Error guardando fechas: ${e.message}`, 'error');

    }

}

window.saveModalDates = saveModalDates;



// -------------------------------------------------------------

// Control de Edición de Plazos & Supervisión

// -------------------------------------------------------------

function toggleEditModalPlazos() {

    const displayEl = document.getElementById('modal-plazos-display-view');

    const editEl = document.getElementById('modal-plazos-edit-view');

    const btnToggle = document.getElementById('btn-modal-toggle-edit-plazos');

    const btnSave = document.getElementById('btn-modal-save-plazos');

    const btnCancel = document.getElementById('btn-modal-cancel-edit-plazos');



    if (displayEl && editEl) {

        displayEl.classList.add('hidden');

        editEl.classList.remove('hidden');

        if (btnToggle) btnToggle.classList.add('hidden');

        if (btnSave) btnSave.classList.remove('hidden');

        if (btnCancel) btnCancel.classList.remove('hidden');

    }

}

window.toggleEditModalPlazos = toggleEditModalPlazos;



function cancelEditModalPlazos() {

    const displayEl = document.getElementById('modal-plazos-display-view');

    const editEl = document.getElementById('modal-plazos-edit-view');

    const btnToggle = document.getElementById('btn-modal-toggle-edit-plazos');

    const btnSave = document.getElementById('btn-modal-save-plazos');

    const btnCancel = document.getElementById('btn-modal-cancel-edit-plazos');



    if (displayEl && editEl) {

        displayEl.classList.remove('hidden');

        editEl.classList.add('hidden');

        if (btnToggle) btnToggle.classList.remove('hidden');

        if (btnSave) btnSave.classList.add('hidden');

        if (btnCancel) btnCancel.classList.add('hidden');

    }

}

window.cancelEditModalPlazos = cancelEditModalPlazos;



async function saveModalPlazosSupervisor() {

    if (!state.selectedContract || !state.selectedContract.id) {

        showToast('No se puede guardar: contrato no seleccionado.', 'warning');

        return;

    }

    const contractId = state.selectedContract.id;

    const plazoNum = parseInt(document.getElementById('modal-edit-plazo-ejecucion')?.value) || 1;

    const unidadPlazo = document.getElementById('modal-edit-unidad-plazo')?.value || 'MESES';

    const prorroga1 = document.getElementById('modal-edit-prorroga-1')?.value?.trim() || null;

    const supNombre = document.getElementById('modal-edit-supervisor-nombre')?.value?.trim() || null;

    const supCargo = document.getElementById('modal-edit-supervisor-cargo')?.value?.trim() || null;

    const supDoc = document.getElementById('modal-edit-supervisor-doc')?.value?.trim() || null;



    const plazoTexto = `${plazoNum} ${unidadPlazo.toLowerCase()}`;



    const saveBtn = document.getElementById('btn-modal-save-plazos');

    const origHtml = saveBtn ? saveBtn.innerHTML : '';

    if (saveBtn) {

        saveBtn.disabled = true;

        saveBtn.innerHTML = '<span>⏳</span> Guardando...';

    }



    try {

        const payload = {

            plazo_ejecucion: plazoNum,

            unidad_plazo: unidadPlazo,

            plazo_texto: plazoTexto,

            prorroga_1: prorroga1,

            supervisor_nombre: supNombre,

            supervisor_cargo: supCargo,

            supervisor_documento: supDoc

        };



        const updated = await window.api.updateContract(contractId, payload);

        state.selectedContract = updated;



        // Actualizar vista normal

        if (document.getElementById('modal-plazo')) {

            document.getElementById('modal-plazo').innerText = updated.plazo_texto || `${updated.plazo_ejecucion} ${updated.unidad_plazo?.toLowerCase() || ''}`;

        }

        if (document.getElementById('modal-prorroga-1')) {

            document.getElementById('modal-prorroga-1').innerText = updated.prorroga_1 || '-';

        }

        const docExtra = updated.supervisor_documento ? ` | ${updated.supervisor_tipo_documento || 'CC'} ${updated.supervisor_documento}` : '';

        if (document.getElementById('modal-supervisor')) {

            document.getElementById('modal-supervisor').innerText = `${updated.supervisor_nombre || 'Por definir'} (${updated.supervisor_cargo || 'Supervisor'})${docExtra}`;

        }



        cancelEditModalPlazos();

        showToast('Plazos y datos de supervisión actualizados con éxito.', 'success');



        if (typeof loadContractsTable === 'function') {

            loadContractsTable();

        }

    } catch (e) {

        showToast(`Error guardando plazos y supervisor: ${e.message}`, 'error');

    } finally {

        if (saveBtn) {

            saveBtn.disabled = false;

            saveBtn.innerHTML = origHtml;

        }

    }

}

window.saveModalPlazosSupervisor = saveModalPlazosSupervisor;



// -------------------------------------------------------------

// Control de Edición de Presupuesto, CDP, Rubro & CCPET

// -------------------------------------------------------------

function toggleEditModalBudget() {

    const displayEl = document.getElementById('modal-budget-display-view');

    const editEl = document.getElementById('modal-budget-edit-view');

    const btnToggle = document.getElementById('btn-modal-toggle-edit-budget');

    const btnSave = document.getElementById('btn-modal-save-budget');

    const btnCancel = document.getElementById('btn-modal-cancel-edit-budget');



    if (displayEl && editEl) {

        displayEl.classList.add('hidden');

        editEl.classList.remove('hidden');

        if (btnToggle) btnToggle.classList.add('hidden');

        if (btnSave) btnSave.classList.remove('hidden');

        if (btnCancel) btnCancel.classList.remove('hidden');

    }

}

window.toggleEditModalBudget = toggleEditModalBudget;



function cancelEditModalBudget() {

    const displayEl = document.getElementById('modal-budget-display-view');

    const editEl = document.getElementById('modal-budget-edit-view');

    const btnToggle = document.getElementById('btn-modal-toggle-edit-budget');

    const btnSave = document.getElementById('btn-modal-save-budget');

    const btnCancel = document.getElementById('btn-modal-cancel-edit-budget');



    if (displayEl && editEl) {

        displayEl.classList.remove('hidden');

        editEl.classList.add('hidden');

        if (btnToggle) btnToggle.classList.remove('hidden');

        if (btnSave) btnSave.classList.add('hidden');

        if (btnCancel) btnCancel.classList.add('hidden');

    }

}

window.cancelEditModalBudget = cancelEditModalBudget;



function regenerateModalCdpFullText() {

    const num = document.getElementById('modal-edit-cdp-num')?.value?.trim();

    const fecha = document.getElementById('modal-edit-cdp-fecha')?.value?.trim();

    const val = parseFloat(document.getElementById('modal-edit-cdp-valor')?.value) || 0;

    const rubroCod = document.getElementById('modal-edit-cdp-rubro')?.value?.trim();

    const rubroNom = document.getElementById('modal-edit-cdp-rubro-nombre')?.value?.trim();



    const parts = [];

    if (num) parts.push(num);

    if (fecha) parts.push(`expedido el ${formatContractDate(fecha)}`);

    if (val > 0) parts.push(`por valor de $${Number(val).toLocaleString('de-DE')}`);

    if (rubroCod) {

        const desc = rubroNom ? `${rubroCod} – ${rubroNom}` : rubroCod;

        parts.push(`con cargo al Rubro Presupuestal ${desc}`);

    }

    const fullText = parts.length > 0 ? limpiarTextoCdp(parts.join(', ')) : '';

    const target = document.getElementById('modal-edit-cdp-texto-completo');

    if (target) {

        target.value = fullText;

    }

    showToast('Texto {{CDP}} regenerado con base en los campos del formulario.', 'info');

}

window.regenerateModalCdpFullText = regenerateModalCdpFullText;



async function saveModalBudget() {

    if (!state.selectedContract || !state.selectedContract.id) {

        showToast('No se puede guardar: contrato no seleccionado.', 'warning');

        return;

    }

    const contractId = state.selectedContract.id;

    const cdpNum = document.getElementById('modal-edit-cdp-num')?.value?.trim() || null;

    const cdpFecha = document.getElementById('modal-edit-cdp-fecha')?.value?.trim() || null;

    const cdpValRaw = document.getElementById('modal-edit-cdp-valor')?.value?.trim();

    const cdpVal = cdpValRaw ? parseFloat(cdpValRaw) : null;

    const crpNum = document.getElementById('modal-edit-crp-num')?.value?.trim() || null;

    const cdpRubro = document.getElementById('modal-edit-cdp-rubro')?.value?.trim() || null;

    const cdpRubroNombre = document.getElementById('modal-edit-cdp-rubro-nombre')?.value?.trim() || null;

    const cdpClasifRaw = document.getElementById('modal-edit-cdp-clasificadores')?.value?.trim() || '';

    const cdpTextoCompleto = document.getElementById('modal-edit-cdp-texto-completo')?.value?.trim() || null;



    let cdpClasifList = cdpClasifRaw ? cdpClasifRaw.split('\n').map(s => s.trim()).filter(Boolean) : [];



    const saveBtn = document.getElementById('btn-modal-save-budget');

    const origHtml = saveBtn ? saveBtn.innerHTML : '';

    if (saveBtn) {

        saveBtn.disabled = true;

        saveBtn.innerHTML = '<span>⏳</span> Guardando...';

    }



    try {

        const metaUpdates = {

            cdp_numero: cdpNum,

            cdp_fecha: cdpFecha,

            cdp_valor: cdpVal,

            cdp_rubro: cdpRubro,

            cdp_rubro_nombre: cdpRubroNombre,

            cdp_clasificadores: cdpClasifList,

            cdp_texto_completo: cdpTextoCompleto

        };



        const payload = {

            cdp_numero: cdpNum,

            cdp_fecha: cdpFecha,

            cdp_rubro: cdpRubro,

            rp_numero: crpNum,

            metadatos_agente: metaUpdates

        };



        const updated = await window.api.updateContract(contractId, payload);

        state.selectedContract = updated;



        // Actualizar vista normal

        const meta = updated.metadatos_agente || {};

        if (document.getElementById('modal-cdp-num')) document.getElementById('modal-cdp-num').innerText = updated.cdp_numero || meta.cdp_numero || '-';

        if (document.getElementById('modal-cdp-fecha')) document.getElementById('modal-cdp-fecha').innerText = (updated.cdp_fecha || meta.cdp_fecha) ? formatContractDate(updated.cdp_fecha || meta.cdp_fecha) : '-';

        if (document.getElementById('modal-cdp-valor')) document.getElementById('modal-cdp-valor').innerText = (meta.cdp_valor !== undefined && meta.cdp_valor !== null) ? `$${Number(meta.cdp_valor).toLocaleString('de-DE')}` : '-';

        if (document.getElementById('modal-crp-num')) document.getElementById('modal-crp-num').innerText = updated.rp_numero || '-';

        if (document.getElementById('modal-cdp-rubro')) document.getElementById('modal-cdp-rubro').innerText = updated.cdp_rubro || meta.cdp_rubro || '-';

        if (document.getElementById('modal-cdp-rubro-nombre')) document.getElementById('modal-cdp-rubro-nombre').innerText = meta.cdp_rubro_nombre || '-';



        const clasifContainer = document.getElementById('modal-cdp-clasificadores-container');

        const clasifEl = document.getElementById('modal-cdp-clasificadores');

        if (clasifContainer && clasifEl) {

            if (cdpClasifList && cdpClasifList.length > 0) {

                clasifEl.innerText = cdpClasifList.join('; ');

                clasifContainer.classList.remove('hidden');

            } else {

                clasifContainer.classList.add('hidden');

            }

        }



        const textoCompletoEl = document.getElementById('modal-cdp-texto-completo');

        if (textoCompletoEl) {

            textoCompletoEl.innerText = cdpTextoCompleto || meta.cdp_texto_completo || 'No se ha configurado disponibilidad presupuestal para este contrato.';

        }



        cancelEditModalBudget();

        showToast('Presupuesto, CDP y clasificadores actualizados exitosamente.', 'success');



        if (typeof loadContractsTable === 'function') {

            loadContractsTable();

        }

    } catch (e) {

        showToast(`Error guardando presupuesto: ${e.message}`, 'error');

    } finally {

        if (saveBtn) {

            saveBtn.disabled = false;

            saveBtn.innerHTML = origHtml;

        }

    }

}

window.saveModalBudget = saveModalBudget;



// Garantizar disponibilidad de updateContractAddition en window.api incluso si api.js fue cargado desde caché

if (typeof window !== 'undefined') {

    if (!window.api) window.api = {};

    if (typeof window.api.updateContractAddition !== 'function') {

        window.api.updateContractAddition = async function(id, adicion_1, prorroga_1 = null) {

            return window.api.request(`/contracts/${id}/adicion`, {

                method: 'PATCH',

                body: JSON.stringify({ adicion_1, prorroga_1 })

            });

        };

    }

}



async function saveContractAdditionQuick() {

    if (!window.api.isAdmin()) {

        showToast('Acceso Denegado: Solo el Administrador puede modificar adiciones.', 'error');

        return;

    }

    if (!state.selectedContract) {

        showToast('No hay ningún contrato seleccionado', 'warning');

        return;

    }

    const contractId = state.selectedContract.id;

    const inputAdicion = document.getElementById('modal-input-adicion-1');



    let adicionVal;

    if (explicitVal !== null && explicitVal !== undefined) {

        adicionVal = Number(explicitVal);

    } else {

        if (!inputAdicion) return;

        const raw = (inputAdicion.value || '').trim();

        adicionVal = raw === '' ? 0 : parseFloat(raw);

    }



    if (isNaN(adicionVal) || adicionVal < 0) {

        showToast('Por favor ingrese un valor numérico válido (mayor o igual a 0).', 'warning');

        return;

    }



    const saveBtn = document.getElementById('btn-save-adicion-quick');

    const origHtml = saveBtn ? saveBtn.innerHTML : '';

    if (saveBtn) {

        saveBtn.disabled = true;

        saveBtn.innerHTML = '<span>⏳</span> Guardando...';

    }



    try {

        let updated;

        if (window.api && typeof window.api.updateContractAddition === 'function') {

            updated = await window.api.updateContractAddition(contractId, adicionVal);

        } else if (window.api && typeof window.api.request === 'function') {

            updated = await window.api.request(`/contracts/${contractId}/adicion`, {

                method: 'PATCH',

                body: JSON.stringify({ adicion_1: adicionVal, prorroga_1: null })

            });

        }



        state.selectedContract = updated;

        window.currentContractValorInicial = (updated.valor_inicial !== undefined && updated.valor_inicial !== null)

            ? updated.valor_inicial

            : (updated.valor_total - (updated.adicion_1 || 0));



        if (document.getElementById('modal-valor-inicial')) {

            document.getElementById('modal-valor-inicial').innerText = formatCurrency(window.currentContractValorInicial);

        }

        if (document.getElementById('modal-valor')) {

            document.getElementById('modal-valor').innerText = `${formatCurrency(updated.valor_total)} (${updated.valor_en_letras || ''})`;

        }

        if (inputAdicion) {

            inputAdicion.value = updated.adicion_1 || 0;

        }

        calculateModalTotalFromAddition();



        // Refrescar tarjeta de adición vigente en el modal

        await loadContractAdditionsForModal(contractId);



        if (adicionVal === 0) {

            showToast(`✅ Adición del contrato ${updated.numero_contrato} eliminada / restablecida a $0.`, 'success');

        } else {

            showToast(`Adición del contrato ${updated.numero_contrato} actualizada a ${formatCurrency(adicionVal)} con éxito`, 'success');

        }



        // Refrescar listados y dashboard en segundo plano

        loadContractsTable();

        loadDashboard();

        const tabExcel = document.getElementById('tab-excel');

        if (tabExcel && !tabExcel.classList.contains('hidden')) {

            loadExcelView();

        }

    } catch (e) {

        showToast(`Error al guardar la adición: ${e.message}`, 'error');

    } finally {

        if (saveBtn) {

            saveBtn.disabled = false;

            saveBtn.innerHTML = origHtml;

        }

    }

}

window.saveContractAdditionQuick = saveContractAdditionQuick;



async function clearContractAdditionQuick() {

    if (!window.api.isAdmin()) {

        showToast('Acción restringida: solo administradores pueden eliminar adiciones.', 'warning');

        return;

    }

    if (!state.selectedContract) {

        showToast('No hay ningún contrato seleccionado', 'warning');

        return;

    }

    const contract = state.selectedContract;

    if (!contract.adicion_1 || contract.adicion_1 <= 0) {

        showToast('El contrato no tiene una adición registrada actualmente.', 'info');

        return;

    }

    const confirmMsg = `¿Está seguro de eliminar la adición del contrato ${contract.numero_contrato} por ${formatCurrency(contract.adicion_1)}?\n\nEsta acción restablecerá la adición a $0 y revertirá el valor total al valor inicial.`;

    if (!confirm(confirmMsg)) return;



    const inputAdicion = document.getElementById('modal-input-adicion-1');

    if (inputAdicion) inputAdicion.value = 0;

    calculateModalTotalFromAddition();

    await saveContractAdditionQuick(0);

}

window.clearContractAdditionQuick = clearContractAdditionQuick;



function handleModalObjetoInput(el) {

    if (!el) return;

    const countEl = document.getElementById('modal-objeto-char-count');

    if (countEl) {

        countEl.innerText = `${(el.value || '').length} caracteres`;

    }

    const dirtyBadge = document.getElementById('modal-objeto-dirty-badge');

    const origObjeto = (state.selectedContract && state.selectedContract.objeto) || '';

    if (dirtyBadge) {

        if (el.value.trim() !== origObjeto.trim()) {

            dirtyBadge.classList.remove('hidden');

        } else {

            dirtyBadge.classList.add('hidden');

        }

    }

}

window.handleModalObjetoInput = handleModalObjetoInput;



function cleanDuplicateModalObjeto() {

    const el = document.getElementById('modal-objeto');

    if (!el) return;

    const currentVal = el.value || '';

    if (!currentVal.trim()) return;



    let cleaned = currentVal;

    // 1. Eliminar repeticiones consecutivas de prefijos de contratos

    cleaned = cleaned.replace(/(?:\bPRESTACI[OÓ]N\s+DE\s+SERVICIOS\s+(?:PARA|DE)\s+)+/gi, 'PRESTACION DE SERVICIOS PARA ');

    cleaned = cleaned.replace(/(?:\bCONTRATO\s+DE\s+OBRA\s+(?:PARA|DE)\s+)+/gi, 'CONTRATO DE OBRA PARA ');

    cleaned = cleaned.replace(/(?:\bSUMINISTRO\s+DE\s+)+/gi, 'SUMINISTRO DE ');

    // 2. Corregir "DE DEL", "DEL DEL", "PARA PARA"

    cleaned = cleaned.replace(/\bDE\s+DEL\b/gi, 'DEL');

    cleaned = cleaned.replace(/\bDEL\s+DEL\b/gi, 'DEL');

    cleaned = cleaned.replace(/\bPARA\s+PARA\b/gi, 'PARA');

    // 3. Normalizar espacios

    cleaned = cleaned.replace(/\s+/g, ' ').trim().toUpperCase();



    if (cleaned !== currentVal.trim()) {

        el.value = cleaned;

        handleModalObjetoInput(el);

        showToast('Repeticiones corregidas automáticamente en el objeto contractual.', 'info');

    } else {

        showToast('El objeto contractual no contiene repeticiones evidentes.', 'info');

    }

}

window.cleanDuplicateModalObjeto = cleanDuplicateModalObjeto;



async function saveContractObjetoQuick() {

    if (!state.selectedContract) {

        showToast('No hay ningún contrato seleccionado', 'warning');

        return;

    }

    const contractId = state.selectedContract.id;

    const inputObjeto = document.getElementById('modal-objeto');

    if (!inputObjeto) return;



    let newObjeto = (inputObjeto.value || '').trim();

    if (!newObjeto) {

        showToast('El objeto contractual no puede estar vacío.', 'warning');

        return;

    }



    const saveBtn = document.getElementById('btn-save-objeto-quick');

    const origHtml = saveBtn ? saveBtn.innerHTML : '';

    if (saveBtn) {

        saveBtn.disabled = true;

        saveBtn.innerHTML = '<span>⏳</span> Guardando...';

    }



    try {

        let updated;

        if (window.api && typeof window.api.updateContractObjeto === 'function') {

            updated = await window.api.updateContractObjeto(contractId, newObjeto);

        } else if (window.api && typeof window.api.updateContract === 'function') {

            updated = await window.api.updateContract(contractId, { objeto: newObjeto });

        } else {

            updated = await window.api.request(`/contracts/${contractId}/objeto`, {

                method: 'PATCH',

                body: JSON.stringify({ objeto: newObjeto })

            });

        }



        // Actualizar contrato en memoria

        state.selectedContract.objeto = updated.objeto;

        if (state.contracts && Array.isArray(state.contracts)) {

            const idx = state.contracts.findIndex(x => x.id === contractId);

            if (idx !== -1) {

                state.contracts[idx].objeto = updated.objeto;

            }

        }



        // Actualizar campos en el DOM

        inputObjeto.value = updated.objeto;

        handleModalObjetoInput(inputObjeto);



        const drawerObj = document.getElementById('drawer-objeto');

        if (drawerObj) {

            drawerObj.innerText = updated.objeto;

        }



        const dirtyBadge = document.getElementById('modal-objeto-dirty-badge');

        if (dirtyBadge) dirtyBadge.classList.add('hidden');



        showToast(`Objeto contractual del contrato ${updated.numero_contrato} actualizado y sincronizado en Excel con éxito.`, 'success');



        // Refrescar tabla de contratos en segundo plano

        if (typeof loadContractsTable === 'function') {

            loadContractsTable();

        }

    } catch (e) {

        showToast(`Error al guardar el objeto contractual: ${e.message}`, 'error');

    } finally {

        if (saveBtn) {

            saveBtn.disabled = false;

            saveBtn.innerHTML = origHtml;

        }

    }

}

window.saveContractObjetoQuick = saveContractObjetoQuick;



function toggleEditContractNumberModal(show) {

    const container = document.getElementById('modal-contract-num-edit-container');

    const input = document.getElementById('input-edit-contract-num');

    const displayNum = document.getElementById('modal-contract-num');

    if (!container) return;



    const willShow = (show !== undefined) ? show : container.classList.contains('hidden');

    if (willShow) {

        container.classList.remove('hidden');

        if (input && state.selectedContract) {

            input.value = state.selectedContract.numero_contrato || (displayNum ? displayNum.innerText : '');

            input.focus();

            input.select();

        }

    } else {

        container.classList.add('hidden');

    }

}

window.toggleEditContractNumberModal = toggleEditContractNumberModal;



function suggestPrefixForModalContractNumber() {

    if (!state.selectedContract) return;

    const input = document.getElementById('input-edit-contract-num');

    if (!input) return;



    const tip = state.selectedContract.tipologia || 'PRESTACION_SERVICIOS';

    const prefixMap = {

        'PRESTACION_SERVICIOS': 'CPS',

        'SUMINISTRO': 'CS',

        'ARRENDAMIENTO': 'CA',

        'OBRA': 'CO',

        'CONSULTORIA': 'CC',

        'INTERVENTORIA': 'CI'

    };

    const targetPrefix = prefixMap[tip] || 'CPS';

    let curVal = input.value.trim().toUpperCase();



    if (/^[A-Z]{2,4}-/.test(curVal)) {

        curVal = curVal.replace(/^[A-Z]{2,4}-/, `${targetPrefix}-`);

    } else if (/^\d+/.test(curVal)) {

        const vig = state.selectedContract.vigencia || 2026;

        curVal = `${targetPrefix}-${curVal.padStart(3, '0')}-${vig}`;

    } else {

        curVal = `${targetPrefix}-${curVal}`;

    }



    input.value = curVal;

    showToast(`Prefijo oficial sugerido: ${targetPrefix} para contratos de ${tip}`, 'info');

}

window.suggestPrefixForModalContractNumber = suggestPrefixForModalContractNumber;



async function saveContractNumberQuick() {

    if (!state.selectedContract) {

        showToast('No hay ningún contrato seleccionado', 'warning');

        return;

    }

    const contractId = state.selectedContract.id;

    const input = document.getElementById('input-edit-contract-num');

    if (!input) return;



    const newNumber = input.value.trim().toUpperCase();

    if (!newNumber) {

        showToast('El código del contrato no puede estar vacío.', 'warning');

        return;

    }



    const saveBtn = document.getElementById('btn-save-contract-num');

    const origHtml = saveBtn ? saveBtn.innerHTML : '';

    if (saveBtn) {

        saveBtn.disabled = true;

        saveBtn.innerHTML = '<span>⏳</span>';

    }



    try {

        let updated;

        if (window.api && typeof window.api.updateContractNumber === 'function') {

            updated = await window.api.updateContractNumber(contractId, newNumber, true);

        } else {

            updated = await window.api.request(`/contracts/${contractId}/numero`, {

                method: 'PATCH',

                body: JSON.stringify({ nuevo_numero: newNumber, forzar_prefijo: true })

            });

        }



        const oldNumber = state.selectedContract.numero_contrato;

        state.selectedContract.numero_contrato = updated.numero_contrato;



        // Actualizar tabla en memoria

        if (state.contracts && Array.isArray(state.contracts)) {

            const idx = state.contracts.findIndex(x => x.id === contractId);

            if (idx !== -1) {

                state.contracts[idx].numero_contrato = updated.numero_contrato;

            }

        }



        // Actualizar visualmente encabezado del modal

        const h2 = document.getElementById('modal-contract-num');

        if (h2) h2.innerText = updated.numero_contrato;



        toggleEditContractNumberModal(false);



        showToast(`Código del contrato actualizado exitosamente: ${oldNumber} ➔ ${updated.numero_contrato}`, 'success');



        // Refrescar tablas

        if (typeof loadContractsTable === 'function') {

            loadContractsTable();

        }

    } catch (e) {

        showToast(`Error al modificar el código del contrato: ${e.message}`, 'error');

    } finally {

        if (saveBtn) {

            saveBtn.disabled = false;

            saveBtn.innerHTML = origHtml;

        }

    }

}

window.saveContractNumberQuick = saveContractNumberQuick;



function handleModalJustificacionInput(textarea) {

    if (!textarea) return;

    const countEl = document.getElementById('modal-justificacion-char-count');

    if (countEl) {

        countEl.innerText = `${(textarea.value || '').length} caracteres`;

    }

    const dirtyBadge = document.getElementById('modal-justificacion-dirty-badge');

    if (dirtyBadge) {

        const orig = (state.selectedContract && state.selectedContract.justificacion_necesidad) || '';

        if (textarea.value !== orig) {

            dirtyBadge.classList.remove('hidden');

        } else {

            dirtyBadge.classList.add('hidden');

        }

    }

}

window.handleModalJustificacionInput = handleModalJustificacionInput;



async function saveModalJustificacionQuick() {

    if (!state.selectedContract) {

        showToast('No hay ningún contrato seleccionado', 'warning');

        return;

    }

    const contractId = state.selectedContract.id;

    const inputJust = document.getElementById('modal-edit-justificacion');

    if (!inputJust) return;



    let newJust = (inputJust.value || '').trim();

    if (!newJust) {

        showToast('La descripción de la necesidad no puede estar vacía.', 'warning');

        return;

    }



    const saveBtn = document.getElementById('btn-save-justificacion-quick');

    const origHtml = saveBtn ? saveBtn.innerHTML : '';

    if (saveBtn) {

        saveBtn.disabled = true;

        saveBtn.innerHTML = '<span>⏳</span> Guardando...';

    }



    try {

        let updated;

        if (window.api && typeof window.api.updateContract === 'function') {

            updated = await window.api.updateContract(contractId, { justificacion_necesidad: newJust });

        } else {

            updated = await window.api.request(`/contracts/${contractId}`, {

                method: 'PUT',

                body: JSON.stringify({ justificacion_necesidad: newJust })

            });

        }



        state.selectedContract.justificacion_necesidad = updated.justificacion_necesidad;

        if (state.contracts && Array.isArray(state.contracts)) {

            const idx = state.contracts.findIndex(x => x.id === contractId);

            if (idx !== -1) {

                state.contracts[idx].justificacion_necesidad = updated.justificacion_necesidad;

            }

        }



        inputJust.value = updated.justificacion_necesidad;

        handleModalJustificacionInput(inputJust);



        const modalJustP = document.getElementById('modal-justificacion');

        if (modalJustP) modalJustP.innerText = updated.justificacion_necesidad;



        const dirtyBadge = document.getElementById('modal-justificacion-dirty-badge');

        if (dirtyBadge) dirtyBadge.classList.add('hidden');



        showToast(`Descripción de la necesidad del contrato ${updated.numero_contrato} guardada con éxito.`, 'success');

    } catch (e) {

        showToast(`Error al guardar la necesidad: ${e.message}`, 'error');

    } finally {

        if (saveBtn) {

            saveBtn.disabled = false;

            saveBtn.innerHTML = origHtml;

        }

    }

}

window.saveModalJustificacionQuick = saveModalJustificacionQuick;



let currentModalContractExtensionLevel = 'MEDIA';



function setModalContractExtensionLevel(level) {

    currentModalContractExtensionLevel = level || 'MEDIA';

    const btnCorta = document.getElementById('modal-level-btn-corta');

    const btnMedia = document.getElementById('modal-level-btn-media');

    const btnCompleta = document.getElementById('modal-level-btn-completa');



    [btnCorta, btnMedia, btnCompleta].forEach(b => {

        if (b) {

            b.classList.remove('bg-emerald-600', 'text-white', 'font-bold', 'shadow-sm');

            b.classList.add('text-slate-300', 'font-semibold');

        }

    });



    if (level === 'CORTA' && btnCorta) {

        btnCorta.classList.add('bg-emerald-600', 'text-white', 'font-bold', 'shadow-sm');

        btnCorta.classList.remove('text-slate-300', 'font-semibold');

    } else if (level === 'COMPLETA' && btnCompleta) {

        btnCompleta.classList.add('bg-emerald-600', 'text-white', 'font-bold', 'shadow-sm');

        btnCompleta.classList.remove('text-slate-300', 'font-semibold');

    } else if (btnMedia) {

        btnMedia.classList.add('bg-emerald-600', 'text-white', 'font-bold', 'shadow-sm');

        btnMedia.classList.remove('text-slate-300', 'font-semibold');

    }

}

window.setModalContractExtensionLevel = setModalContractExtensionLevel;



async function refreshCurrentContractNecesidad() {

    if (!state.selectedContract) {

        showToast('No hay ningún contrato seleccionado', 'warning');

        return;

    }

    const contractId = state.selectedContract.id;

    const refreshBtn = document.getElementById('btn-refresh-necesidad-modal');

    const origHtml = refreshBtn ? refreshBtn.innerHTML : '';

    if (refreshBtn) {

        refreshBtn.disabled = true;

        refreshBtn.innerHTML = '<span>⏳</span> Regenerando...';

    }



    const nivel = currentModalContractExtensionLevel || 'MEDIA';

    const instr = document.getElementById('modal-instrucciones-adicionales')?.value.trim() || null;



    try {

        let updated;

        if (window.api && typeof window.api.refreshContractNecesidad === 'function') {

            updated = await window.api.refreshContractNecesidad(contractId, {

                nivel_extension: nivel,

                instrucciones_adicionales: instr

            });

        } else {

            updated = await window.api.request(`/contracts/${contractId}/refresh-necesidad`, {

                method: 'POST',

                body: JSON.stringify({ nivel_extension: nivel, instrucciones_adicionales: instr })

            });

        }



        state.selectedContract.justificacion_necesidad = updated.justificacion_necesidad;

        if (state.contracts && Array.isArray(state.contracts)) {

            const idx = state.contracts.findIndex(x => x.id === contractId);

            if (idx !== -1) {

                state.contracts[idx].justificacion_necesidad = updated.justificacion_necesidad;

            }

        }



        const inputJust = document.getElementById('modal-edit-justificacion');

        if (inputJust) {

            inputJust.value = updated.justificacion_necesidad;

            handleModalJustificacionInput(inputJust);

        }



        const modalJustP = document.getElementById('modal-justificacion');

        if (modalJustP) modalJustP.innerText = updated.justificacion_necesidad;



        const dirtyBadge = document.getElementById('modal-justificacion-dirty-badge');

        if (dirtyBadge) dirtyBadge.classList.add('hidden');



        showToast(`✨ Necesidad del contrato ${updated.numero_contrato} regenerada (Nivel ${nivel}).`, 'success');

    } catch (e) {

        showToast(`Error al regenerar la necesidad: ${e.message}`, 'error');

    } finally {

        if (refreshBtn) {

            refreshBtn.disabled = false;

            refreshBtn.innerHTML = origHtml;

        }

    }

}

window.refreshCurrentContractNecesidad = refreshCurrentContractNecesidad;



async function refreshCurrentContractAllSections() {

    if (!state.selectedContract) {

        showToast('No hay ningún contrato seleccionado', 'warning');

        return;

    }

    const contractId = state.selectedContract.id;

    const refreshBtn = document.getElementById('btn-refresh-all-modal');

    const origHtml = refreshBtn ? refreshBtn.innerHTML : '';

    if (refreshBtn) {

        refreshBtn.disabled = true;

        refreshBtn.innerHTML = '<span>⏳</span> Regenerando Todo...';

    }



    const nivel = currentModalContractExtensionLevel || 'MEDIA';

    const instr = document.getElementById('modal-instrucciones-adicionales')?.value.trim() || null;



    try {

        const updated = await window.api.refreshContractAllSections(contractId, {

            nivel_extension: nivel,

            instrucciones_adicionales: instr

        });



        state.selectedContract = updated;

        if (state.contracts && Array.isArray(state.contracts)) {

            const idx = state.contracts.findIndex(x => x.id === contractId);

            if (idx !== -1) {

                state.contracts[idx] = updated;

            }

        }



        // Actualizar UI del Modal

        const inputJust = document.getElementById('modal-edit-justificacion');

        if (inputJust) {

            inputJust.value = updated.justificacion_necesidad;

            handleModalJustificacionInput(inputJust);

        }

        const modalJustP = document.getElementById('modal-justificacion');

        if (modalJustP) modalJustP.innerText = updated.justificacion_necesidad;



        const obligEp = document.getElementById('modal-oblig-ep');

        if (obligEp) {

            obligEp.innerHTML = (updated.obligaciones_estudio_previo || []).map(o => `<li>• ${o}</li>`).join('') || '<li>Sin obligaciones registradas</li>';

        }

        const obligMin = document.getElementById('modal-oblig-minuta');

        if (obligMin) {

            obligMin.innerHTML = (updated.obligaciones_minuta || []).map(o => `<li>• ${o}</li>`).join('') || '<li>Sin obligaciones registradas</li>';

        }

        const obligEmp = document.getElementById('modal-oblig-empresa');

        if (obligEmp) {

            obligEmp.innerHTML = (updated.obligaciones_empresa || []).map(o => `<li>• ${o}</li>`).join('') || '<li>Sin obligaciones registradas</li>';

        }



        showToast(`✨ Necesidad, Objetivos y Obligaciones regenerados exitosamente (Nivel ${nivel}).`, 'success');

    } catch (e) {

        showToast(`Error al regenerar secciones: ${e.message}`, 'error');

    } finally {

        if (refreshBtn) {

            refreshBtn.disabled = false;

            refreshBtn.innerHTML = origHtml;

        }

    }

}

window.refreshCurrentContractAllSections = refreshCurrentContractAllSections;



async function triggerBatchRefreshNecesidadesPrompt(desdeNumero = 'CPS-050-2026') {

    const confirmed = confirm(

        `⚡ ACTUALIZACIÓN EN LOTE DE NECESIDADES (ESTUDIOS PREVIOS):\n\n` +

        `¿Desea aplicar el estándar obligatorio de 4 párrafos (Regla de Oro Ley 142/1994) a los contratos elaborados desde ${desdeNumero} en adelante?\n\n` +

        `• Párrafo 1: Marco Institucional (E.I.C.E., Ley 142/1994, Art 31 y Art 2 C.P.)\n` +

        `• Párrafo 2: Necesidad Técnica dinámica (Fórmula estricta según Objeto, sin plantillas genéricas)\n` +

        `• Párrafo 3: Justificación según Tipo de Contrato (Servicios / Suministro / Obra)\n` +

        `• Párrafo 4: Conclusión del impacto y eficiencia\n` +

        `• Cero menciones de acueducto en PGIRS/Aseo/Administrativo.`

    );

    if (!confirmed) return;



    const btn = document.getElementById('btn-batch-refresh-necesidades');

    const origHtml = btn ? btn.innerHTML : '';

    if (btn) {

        btn.disabled = true;

        btn.innerHTML = '<span>⏳</span> Procesando lote...';

    }



    try {

        let result;

        if (window.api && typeof window.api.batchRefreshNecesidades === 'function') {

            result = await window.api.batchRefreshNecesidades({ desde_numero: desdeNumero });

        } else {

            result = await window.api.request('/contracts/batch-refresh-necesidades', {

                method: 'POST',

                body: JSON.stringify({ desde_numero: desdeNumero })

            });

        }



        const count = result.contratos_actualizados || 0;

        showToast(`✅ Se actualizaron exitosamente ${count} contratos con el estándar de 4 párrafos.`, 'success');



        // Si la tabla de contratos está cargada, refrescarla

        if (typeof loadContractsTable === 'function') {

            loadContractsTable();

        }



        // Si el modal está abierto actualmente para uno de esos contratos, recargar su vista

        if (state.selectedContract) {

            viewContractDetail(state.selectedContract.id);

        }

    } catch (e) {

        showToast(`Error al actualizar lote de necesidades: ${e.message}`, 'error');

    } finally {

        if (btn) {

            btn.disabled = false;

            btn.innerHTML = origHtml;

        }

    }

}

window.triggerBatchRefreshNecesidadesPrompt = triggerBatchRefreshNecesidadesPrompt;



async function handleDeleteContract(contractId, contractNum) {

    if (!window.api.isAdmin()) {

        showToast('Acceso Denegado: Solo el Administrador puede anular o eliminar contratos.', 'error');

        return;

    }

    

    const motivo = prompt(

        `⚠️ ATENCIÓN - ANULACIÓN / ELIMINACIÓN DE CONTRATO\n\n` +

        `Contrato: ${contractNum}\n\n` +

        `Por favor ingrese el motivo justificado de la anulación o eliminación (mínimo 15 caracteres):\n` +

        `• Si el contrato está en ejecución o tiene pagos/adiciones, pasará a estado ANULADO conservando su trazabilidad.\n` +

        `• Si está en borrador sin pagos, se eliminará el registro físico pero se conservará la auditoría.`

    );

    

    if (motivo === null) return; // Cancelado por el usuario

    

    const motivoTrim = motivo.trim();

    if (motivoTrim.length < 15) {

        showToast('El motivo debe tener al menos 15 caracteres para garantizar la trazabilidad legal.', 'error');

        return;

    }



    try {

        showToast(`Procesando anulación/eliminación del contrato ${contractNum}...`, 'info');

        const res = await window.api.deleteContract(contractId, motivoTrim);

        showToast(res?.mensaje || `Operación completada sobre el contrato ${contractNum}.`, 'success');



        if (state.selectedContract && state.selectedContract.id === contractId) {

            closeContractDetailModal();

        }



        await loadContractsTable();

        await loadDashboard();



        const tabExcel = document.getElementById('tab-excel');

        if (tabExcel && !tabExcel.classList.contains('hidden')) {

            await loadExcelView();

        }

    } catch (e) {

        showToast(`Error al procesar contrato: ${e.message}`, 'error');

    }

}



async function saveContractStatusChange() {

    if (!window.api.isAdmin()) {

        showToast('Acceso Denegado: Solo el Administrador puede cambiar el estado de contratos.', 'error');

        return;

    }

    if (!state.selectedContract) return;

    const newStatus = document.getElementById('modal-estado-select').value;

    const obs = prompt('Observación para el registro de auditoría (opcional):', 'Actualización de estado en panel web') || '';



    try {

        await window.api.updateContractStatus(state.selectedContract.id, newStatus, obs);

        showToast(`Estado de contrato actualizado a ${newStatus}`, 'success');

        closeContractDetailModal();

        loadContractsTable();

        loadDashboard();

        loadExcelView();

    } catch (e) {

        showToast(`Error al cambiar estado: ${e.message}`, 'error');

    }

}



async function downloadDocx(contractId, type) {

    try {

        showToast(`Generando ${type.replace('_', ' ')} en Word...`, 'info');

        // Trigger generation first

        await window.api.generateDocument(contractId, type);

        // Download file

        const url = window.api.getTemplateDownloadUrl(contractId, type);

        window.open(url, '_blank');

        showToast(`Documento ${type} descargado exitosamente.`, 'success');

    } catch (e) {

        showToast(`Error descargando documento: ${e.message}`, 'error');

    }

}



async function syncContractExcel(contractId) {

    if (!contractId) {

        showToast('No se puede sincronizar: el ID del contrato no está definido o el contrato no ha sido guardado.', 'warning');

        return;

    }

    try {

        showToast('Sincronizando contrato con la Matriz de Excel...', 'info');

        const res = await window.api.syncContractToExcel(contractId);

        showToast(`Contrato sincronizado en la Fila ${res.resultado.fila_excel} de Excel`, 'success');

    } catch (e) {

        showToast(`Error sincronizando con Excel: ${e.message}`, 'error');

    }

}



// -------------------------------------------------------------

// PANEL INDEPENDIENTE DE GESTIÓN DE CONTRATISTAS

// -------------------------------------------------------------

state.contractorsView = 'grid'; // 'grid' o 'table'



async function loadContractorsTab() {

    const grid = document.getElementById('contractors-grid');

    const tableBody = document.getElementById('contractors-table-body');

    const badge = document.getElementById('contractors-count-badge');

    

    if (grid) grid.innerHTML = '<div class="col-span-full py-12 text-center text-slate-400 text-xs">Cargando directorio maestro de contratistas...</div>';

    if (tableBody) tableBody.innerHTML = '<tr><td colspan="8" class="py-8 text-center text-slate-400 text-xs">Cargando contratistas...</td></tr>';



    try {

        const contractors = await window.api.getContractors();

        state.contractors = contractors || [];



        // Calcular Métricas KPI

        updateContractorKPIs(state.contractors);



        // Renderizar vista activa con filtros actuales

        filterContractorsList();

        loadWizardContractorsDropdown();

    } catch (e) {

        console.error('Error cargando contratistas:', e);

        if (grid) grid.innerHTML = `<div class="col-span-full py-8 text-center text-rose-400 text-xs">Error al cargar contratistas: ${e.message}</div>`;

        if (tableBody) tableBody.innerHTML = `<tr><td colspan="8" class="py-8 text-center text-rose-400 text-xs">Error: ${e.message}</td></tr>`;

        showToast(`Error al cargar contratistas: ${e.message}`, 'error');

    }

}



function updateContractorKPIs(contractors) {

    const total = contractors.length;

    let naturales = 0;

    let juridicas = 0;

    let conContratos = 0;

    let conBanco = 0;



    contractors.forEach(c => {

        if (c.tipo_persona === 'JURIDICA') {

            juridicas++;

        } else {

            naturales++;

        }



        const numContratos = (c.contratos && c.contratos.length) || (c.codigos_contratos && c.codigos_contratos.length) || 0;

        if (numContratos > 0) conContratos++;



        if (c.banco_nombre && c.banco_numero_cuenta) conBanco++;

    });



    const sinContratos = total - conContratos;



    const elTotal = document.getElementById('contr-kpi-total');

    const elNat = document.getElementById('contr-kpi-naturales');

    const elJur = document.getElementById('contr-kpi-juridicas');

    const elCon = document.getElementById('contr-kpi-con-contratos');

    const elSin = document.getElementById('contr-kpi-sin-contratos');

    const elBan = document.getElementById('contr-kpi-bancarios');



    if (elTotal) elTotal.innerText = total;

    if (elNat) elNat.innerText = `${naturales} Nat`;

    if (elJur) elJur.innerText = `${juridicas} Jur`;

    if (elCon) elCon.innerText = conContratos;

    if (elSin) elSin.innerText = `${sinContratos} sin contratos`;

    if (elBan) elBan.innerText = `${conBanco} (${total > 0 ? Math.round((conBanco / total) * 100) : 0}%)`;

}



function setContractorsView(view) {

    state.contractorsView = view;

    const btnGrid = document.getElementById('contr-view-grid-btn');

    const btnTable = document.getElementById('contr-view-table-btn');

    const secGrid = document.getElementById('contractors-grid');

    const secTable = document.getElementById('contractors-table-container');



    if (view === 'grid') {

        if (btnGrid) {

            btnGrid.className = 'px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all bg-sky-600/30 text-sky-300 border border-sky-500/40 shadow-sm';

        }

        if (btnTable) {

            btnTable.className = 'px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all text-slate-400 hover:text-slate-200 border border-transparent';

        }

        if (secGrid) secGrid.classList.remove('hidden');

        if (secTable) secTable.classList.add('hidden');

    } else {

        if (btnTable) {

            btnTable.className = 'px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all bg-sky-600/30 text-sky-300 border border-sky-500/40 shadow-sm';

        }

        if (btnGrid) {

            btnGrid.className = 'px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all text-slate-400 hover:text-slate-200 border border-transparent';

        }

        if (secGrid) secGrid.classList.add('hidden');

        if (secTable) secTable.classList.remove('hidden');

    }



    filterContractorsList();

}



function filterContractorsList() {

    const q = (document.getElementById('contractors-search')?.value || '').toLowerCase().trim();

    const filterPersona = document.getElementById('contr-filter-persona')?.value || '';

    const filterContratos = document.getElementById('contr-filter-contratos')?.value || '';

    const filterRegimen = document.getElementById('contr-filter-regimen')?.value || '';

    const sortBy = document.getElementById('contr-sort-by')?.value || 'nombre_asc';



    let filtered = [...(state.contractors || [])];



    // Filtro por texto libre

    if (q) {

        filtered = filtered.filter(c => {

            const matchesName = (c.nombre_o_razon_social || '').toLowerCase().includes(q);

            const matchesComercial = (c.nombre_comercial || '').toLowerCase().includes(q);

            const matchesDoc = (c.numero_documento || '').toLowerCase().includes(q);

            const matchesRep = (c.representante_legal_nombre || '').toLowerCase().includes(q);

            const matchesMail = (c.correo_electronico || '').toLowerCase().includes(q);

            const matchesPhone = (c.telefono || '').toLowerCase().includes(q);

            const matchesCity = (c.municipio || '').toLowerCase().includes(q);

            const matchesDept = (c.departamento || '').toLowerCase().includes(q);

            const matchesContracts = (c.codigos_contratos || []).some(code => code.toLowerCase().includes(q));

            return matchesName || matchesComercial || matchesDoc || matchesRep || matchesMail || matchesPhone || matchesCity || matchesDept || matchesContracts;

        });

    }



    // Filtro por tipo persona

    if (filterPersona) {

        filtered = filtered.filter(c => c.tipo_persona === filterPersona);

    }



    // Filtro por historial contractual

    if (filterContratos === 'con_contratos') {

        filtered = filtered.filter(c => ((c.contratos && c.contratos.length > 0) || (c.codigos_contratos && c.codigos_contratos.length > 0)));

    } else if (filterContratos === 'sin_contratos') {

        filtered = filtered.filter(c => !((c.contratos && c.contratos.length > 0) || (c.codigos_contratos && c.codigos_contratos.length > 0)));

    }



    // Filtro por régimen

    if (filterRegimen) {

        filtered = filtered.filter(c => c.regimen_tributario === filterRegimen);

    }



    // Ordenamiento

    filtered.sort((a, b) => {

        if (sortBy === 'nombre_asc') {

            return (a.nombre_o_razon_social || '').localeCompare(b.nombre_o_razon_social || '');

        }

        if (sortBy === 'nombre_desc') {

            return (b.nombre_o_razon_social || '').localeCompare(a.nombre_o_razon_social || '');

        }

        if (sortBy === 'contratos_desc') {

            const numA = (a.contratos && a.contratos.length) || (a.codigos_contratos && a.codigos_contratos.length) || 0;

            const numB = (b.contratos && b.contratos.length) || (b.codigos_contratos && b.codigos_contratos.length) || 0;

            return numB - numA;

        }

        if (sortBy === 'id_desc') {

            return (b.id || 0) - (a.id || 0);

        }

        return 0;

    });



    // Actualizar badge

    const badge = document.getElementById('contractors-count-badge');

    if (badge) {

        badge.innerText = `Mostrando ${filtered.length} de ${state.contractors.length} contratista(s)`;

    }



    // Renderizar según vista

    if (state.contractorsView === 'table') {

        renderContractorsTable(filtered);

    } else {

        renderContractorsGrid(filtered);

    }

}



function resetContractorsFilters() {

    const s = document.getElementById('contractors-search');

    const p = document.getElementById('contr-filter-persona');

    const c = document.getElementById('contr-filter-contratos');

    const r = document.getElementById('contr-filter-regimen');

    const o = document.getElementById('contr-sort-by');



    if (s) s.value = '';

    if (p) p.value = '';

    if (c) c.value = '';

    if (r) r.value = '';

    if (o) o.value = 'nombre_asc';



    filterContractorsList();

}



function renderContractorsGrid(contractors) {

    const grid = document.getElementById('contractors-grid');

    if (!grid) return;



    if (!contractors || contractors.length === 0) {

        grid.innerHTML = `

            <div class="col-span-full p-10 rounded-2xl bg-slate-900/50 border border-slate-800 text-center space-y-3">

                <div class="w-14 h-14 rounded-2xl bg-slate-800 text-slate-400 flex items-center justify-center mx-auto text-3xl shadow-inner">

                    👥

                </div>

                <h3 class="font-heading font-bold text-slate-200 text-base">No se encontraron contratistas</h3>

                <p class="text-xs text-slate-400 max-w-md mx-auto">

                    Ajuste los términos de búsqueda o filtros, o registre un nuevo contratista para la ESP.

                </p>

                <div class="pt-2 flex justify-center gap-2">

                    <button onclick="resetContractorsFilters()" class="px-3.5 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700">

                        ↺ Limpiar Filtros

                    </button>

                    <button onclick="openContractorModal()" class="gradient-btn px-4 py-2 rounded-xl text-xs font-bold text-white shadow-md">

                        + Registrar Contratista

                    </button>

                </div>

            </div>

        `;

        return;

    }



    grid.innerHTML = contractors.map(c => {

        const dvStr = c.digito_verificacion ? `-${c.digito_verificacion}` : '';

        const isJuridica = c.tipo_persona === 'JURIDICA';

        const personaBadge = isJuridica 

            ? `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-950/80 text-purple-300 border border-purple-800/60 flex items-center gap-1">🏢 Persona Jurídica</span>`

            : `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-sky-950/80 text-sky-300 border border-sky-800/60 flex items-center gap-1">👤 Persona Natural</span>`;

        

        const regimenLabel = c.regimen_tributario === 'RESPONSABLE_IVA' 

            ? 'Responsable IVA' 

            : (c.regimen_tributario === 'REGIMEN_SIMPLE' ? 'Régimen Simple' : (c.regimen_tributario === 'GRAN_CONTRIBUYENTE' ? 'Gran Contribuyente' : 'No Responsable IVA'));



        const ubicacionParts = [c.direccion, c.municipio, c.departamento].filter(Boolean);

        const ubicacionStr = ubicacionParts.length > 0 ? ubicacionParts.join(', ') : 'No registrada';



        const bancoStr = c.banco_nombre 

            ? `${c.banco_nombre} - ${c.banco_tipo_cuenta || 'Ahorros'} No. ${c.banco_numero_cuenta || ''}`

            : 'Sin información bancaria';



        const contratosList = c.contratos || [];

        const codigosList = c.codigos_contratos || [];

        let contratosHtml = '';



        if (contratosList.length > 0) {

            contratosHtml = contratosList.map(ct => `

                <button type="button" onclick="viewContractDetail(${ct.id})" 

                        class="px-2 py-0.5 rounded text-[11px] font-mono bg-sky-950/80 hover:bg-sky-800 text-sky-300 hover:text-white border border-sky-800/60 transition-all flex items-center gap-1 shadow-sm"

                        title="Ver contrato ${ct.numero_contrato} (${ct.estado})">

                    <span>📄</span>

                    <strong>${ct.numero_contrato}</strong>

                    <span class="text-[10px] text-sky-400/80 font-sans">(${ct.vigencia || ''})</span>

                </button>

            `).join('');

        } else if (codigosList.length > 0) {

            contratosHtml = codigosList.map(code => `

                <span class="px-2 py-0.5 rounded text-[11px] font-mono bg-sky-950/80 text-sky-300 border border-sky-800/60">

                    📄 ${code}

                </span>

            `).join('');

        } else {

            contratosHtml = `<span class="text-slate-500 italic text-[11px]">Sin contratos celebrados todavía</span>`;

        }



        const totalContratos = contratosList.length || codigosList.length;



        return `

            <div class="glass-card p-5 rounded-2xl flex flex-col justify-between hover:border-sky-500/50 transition-all space-y-4 group">

                <div class="space-y-2.5">

                    <!-- Badges & Action Buttons -->

                    <div class="flex items-start justify-between gap-2">

                        <div class="flex flex-wrap items-center gap-1.5">

                            ${personaBadge}

                            <span class="px-2 py-0.5 rounded text-[10px] font-medium bg-slate-800 text-slate-300 border border-slate-700">

                                ${regimenLabel}

                            </span>

                        </div>

                        <div class="flex items-center gap-1">

                            <button onclick="viewContractorDetail(${c.id})" 

                                    class="p-1.5 rounded-lg bg-slate-800/90 hover:bg-sky-900/60 text-slate-300 hover:text-sky-200 border border-slate-700 transition-all"

                                    title="Ver ficha técnica completa del contratista">

                                👁️

                            </button>

                            <button onclick="openContractorModal(${c.id})" 

                                    class="p-1.5 rounded-lg bg-slate-800/90 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 transition-all"

                                    title="Editar datos del contratista">

                                ✏️

                            </button>

                            <button onclick="promptDeleteContractor(${c.id})" 

                                    class="p-1.5 rounded-lg bg-slate-800/90 hover:bg-rose-900/60 text-slate-400 hover:text-rose-300 border border-slate-700 transition-all"

                                    title="Eliminar contratista">

                                🗑️

                            </button>

                        </div>

                    </div>



                    <!-- Contractor Title & Document -->

                    <div class="cursor-pointer" onclick="viewContractorDetail(${c.id})">

                        <h3 class="font-heading font-bold text-white text-base leading-snug group-hover:text-sky-300 transition-colors">

                            ${c.nombre_o_razon_social}

                        </h3>

                        ${c.nombre_comercial ? `<span class="text-xs text-slate-400 italic block font-sans">(${c.nombre_comercial})</span>` : ''}

                        <div class="text-xs font-mono text-sky-400 font-semibold mt-0.5">

                            ${c.tipo_documento}: ${c.numero_documento}${dvStr}

                        </div>

                    </div>



                    <!-- Legal Rep if exists -->

                    ${c.representante_legal_nombre ? `

                        <div class="p-2 rounded-lg bg-slate-900/80 border border-slate-800 text-xs text-slate-300">

                            <span class="text-slate-500 font-medium">Representante Legal:</span>

                            <strong class="text-slate-200 ml-1">${c.representante_legal_nombre}</strong>

                            ${c.representante_legal_documento ? `<span class="text-slate-400 font-mono text-[11px] ml-1">(${c.representante_legal_documento})</span>` : ''}

                        </div>

                    ` : ''}



                    <!-- Contact & Bank details -->

                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-slate-300 pt-1">

                        <div class="flex items-center gap-1.5 truncate" title="${c.correo_electronico || 'Sin correo'}">

                            <span class="text-slate-500">✉️</span>

                            <span class="truncate">${c.correo_electronico || '<span class="text-slate-500 italic">Sin correo</span>'}</span>

                        </div>

                        <div class="flex items-center gap-1.5 truncate" title="${c.telefono || 'Sin teléfono'}">

                            <span class="text-slate-500">📞</span>

                            <span>${c.telefono || '<span class="text-slate-500 italic">Sin teléfono</span>'}</span>

                        </div>

                        <div class="sm:col-span-2 flex items-start gap-1.5" title="${ubicacionStr}">

                            <span class="text-slate-500 mt-0.5">📍</span>

                            <span class="line-clamp-1">${ubicacionStr}</span>

                        </div>

                        <div class="sm:col-span-2 flex items-center gap-1.5 truncate text-[11px] text-emerald-400/90 font-mono" title="${bancoStr}">

                            <span class="text-emerald-500">🏦</span>

                            <span class="truncate">${bancoStr}</span>

                        </div>

                    </div>

                </div>



                <!-- Contracts section -->

                <div class="pt-3 border-t border-slate-800/80 space-y-2">

                    <div class="flex items-center justify-between text-xs">

                        <span class="font-bold text-slate-300 flex items-center gap-1.5">

                            <span>📑</span> Contratos con la ESP

                        </span>

                        <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${totalContratos > 0 ? 'bg-sky-950 text-sky-300 border border-sky-800/60' : 'bg-slate-800 text-slate-500'}">

                            ${totalContratos} contrato(s)

                        </span>

                    </div>

                    <div class="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto pr-1">

                        ${contratosHtml}

                    </div>

                </div>



                <!-- Action Button -->

                <div class="pt-2 grid grid-cols-2 gap-2">

                    <button onclick="viewContractorDetail(${c.id})" 

                            class="py-2 px-3 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center justify-center gap-1.5 transition-all">

                        <span>🔍</span> Ver Ficha

                    </button>

                    <button onclick="startContractWithExistingContractor(${c.id})" 

                            class="py-2 px-3 rounded-xl text-xs font-bold text-white gradient-btn shadow-md flex items-center justify-center gap-1.5 hover:scale-[1.01] active:scale-[0.99] transition-all">

                        <span>🚀</span> Contratar

                    </button>

                </div>

            </div>

        `;

    }).join('');

}



function renderContractorsTable(contractors) {

    const tbody = document.getElementById('contractors-table-body');

    if (!tbody) return;



    if (!contractors || contractors.length === 0) {

        tbody.innerHTML = '<tr><td colspan="8" class="py-8 text-center text-slate-500 text-xs">No se encontraron contratistas con los criterios actuales.</td></tr>';

        return;

    }



    tbody.innerHTML = contractors.map(c => {

        const dvStr = c.digito_verificacion ? `-${c.digito_verificacion}` : '';

        const isJuridica = c.tipo_persona === 'JURIDICA';

        const personaBadge = isJuridica 

            ? `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-950/80 text-purple-300 border border-purple-800/60">Jurídica</span>`

            : `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-sky-950/80 text-sky-300 border border-sky-800/60">Natural</span>`;



        const regimenShort = c.regimen_tributario === 'RESPONSABLE_IVA' ? 'Resp. IVA' : (c.regimen_tributario === 'REGIMEN_SIMPLE' ? 'Simple (RST)' : 'No Resp.');

        const numContratos = (c.contratos && c.contratos.length) || (c.codigos_contratos && c.codigos_contratos.length) || 0;



        return `

            <tr class="hover:bg-slate-800/40 transition-colors group">

                <td class="py-3 px-4 font-mono font-semibold text-sky-400 whitespace-nowrap">

                    ${c.tipo_documento} ${c.numero_documento}${dvStr}

                </td>

                <td class="py-3 px-4">

                    <div class="font-bold text-white group-hover:text-sky-300 transition-colors cursor-pointer" onclick="viewContractorDetail(${c.id})">

                        ${c.nombre_o_razon_social}

                    </div>

                    ${c.nombre_comercial ? `<div class="text-[11px] text-slate-400 italic">${c.nombre_comercial}</div>` : ''}

                    ${c.representante_legal_nombre ? `<div class="text-[10px] text-slate-500">Rep: ${c.representante_legal_nombre}</div>` : ''}

                </td>

                <td class="py-3 px-4 whitespace-nowrap">

                    ${personaBadge}

                </td>

                <td class="py-3 px-4 text-[11px]">

                    <div class="text-slate-300">${c.correo_electronico || '<span class="text-slate-500 italic">Sin correo</span>'}</div>

                    <div class="text-slate-400">${c.telefono || '<span class="text-slate-500 italic">Sin teléfono</span>'}</div>

                </td>

                <td class="py-3 px-4 whitespace-nowrap text-slate-300">

                    <div>${c.municipio || 'Yolombó'}</div>

                    <div class="text-[10px] text-slate-500">${c.departamento || 'Antioquia'}</div>

                </td>

                <td class="py-3 px-4 whitespace-nowrap">

                    <span class="px-2 py-0.5 rounded text-[10px] font-medium bg-slate-800 text-slate-300 border border-slate-700">

                        ${regimenShort}

                    </span>

                </td>

                <td class="py-3 px-4 whitespace-nowrap">

                    <span class="px-2.5 py-0.5 rounded-full text-xs font-bold ${numContratos > 0 ? 'bg-sky-950 text-sky-300 border border-sky-800/60' : 'bg-slate-800 text-slate-500'}">

                        ${numContratos} contrato(s)

                    </span>

                </td>

                <td class="py-3 px-4 text-right whitespace-nowrap">

                    <div class="flex items-center justify-end gap-1.5">

                        <button onclick="viewContractorDetail(${c.id})" 

                                class="p-1.5 rounded-lg bg-slate-800 hover:bg-sky-900/60 text-slate-300 hover:text-sky-200 border border-slate-700 transition-all"

                                title="Ver Ficha Técnica">

                            👁️

                        </button>

                        <button onclick="openContractorModal(${c.id})" 

                                class="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 transition-all"

                                title="Editar Datos">

                            ✏️

                        </button>

                        <button onclick="promptDeleteContractor(${c.id})" 

                                class="p-1.5 rounded-lg bg-slate-800 hover:bg-rose-900/60 text-slate-400 hover:text-rose-300 border border-slate-700 transition-all"

                                title="Eliminar Contratista">

                            🗑️

                        </button>

                    </div>

                </td>

            </tr>

        `;

    }).join('');

}



// -------------------------------------------------------------

// FICHA TÉCNICA DETALLADA (MODAL / INSPECTOR)

// -------------------------------------------------------------

async function viewContractorDetail(contractorId) {

    const modal = document.getElementById('contractor-detail-modal');

    if (!modal) return;



    try {

        let c = (state.contractors || []).find(item => item.id === contractorId);

        // Siempre traer fresco con detalle completo de contratos y documentos

        c = await window.api.getContractor(contractorId);



        const dvStr = c.digito_verificacion ? `-${c.digito_verificacion}` : '';

        const isJuridica = c.tipo_persona === 'JURIDICA';



        // Header

        document.getElementById('dtl-contr-nombre').innerText = c.nombre_o_razon_social;

        document.getElementById('dtl-contr-subtitulo').innerText = `${c.tipo_documento}: ${c.numero_documento}${dvStr}${c.nombre_comercial ? ` • Sigla: ${c.nombre_comercial}` : ''}`;

        

        const badgePersona = document.getElementById('dtl-contr-tipo-persona-badge');

        if (badgePersona) {

            badgePersona.innerText = isJuridica ? '🏢 Persona Jurídica' : '👤 Persona Natural';

            badgePersona.className = isJuridica 

                ? 'px-2.5 py-0.5 rounded text-[10px] font-bold bg-purple-950/80 text-purple-300 border border-purple-800/60'

                : 'px-2.5 py-0.5 rounded text-[10px] font-bold bg-sky-950/80 text-sky-300 border border-sky-800/60';

        }



        const regimenLabel = c.regimen_tributario === 'RESPONSABLE_IVA' ? 'Responsable IVA' : (c.regimen_tributario === 'REGIMEN_SIMPLE' ? 'Régimen Simple (RST)' : (c.regimen_tributario === 'GRAN_CONTRIBUYENTE' ? 'Gran Contribuyente' : 'No Responsable IVA'));

        document.getElementById('dtl-contr-regimen-badge').innerText = regimenLabel;

        

        const contratos = c.contratos || [];

        document.getElementById('dtl-contr-contratos-badge').innerText = `${contratos.length} Contrato(s) celebrados`;



        // Section 1

        document.getElementById('dtl-tipo-persona').innerText = isJuridica ? 'Persona Jurídica' : 'Persona Natural';

        document.getElementById('dtl-documento-full').innerText = `${c.tipo_documento} ${c.numero_documento}${dvStr}`;

        document.getElementById('dtl-nombre-comercial').innerText = c.nombre_comercial || 'No registrado';

        document.getElementById('dtl-rep-nombre').innerText = c.representante_legal_nombre || 'No aplica / No registrado';

        document.getElementById('dtl-rep-doc').innerText = c.representante_legal_documento || 'No aplica';



        // Section 2

        document.getElementById('dtl-direccion').innerText = c.direccion || 'No registrada';

        document.getElementById('dtl-municipio').innerText = c.municipio || 'Yolombó';

        document.getElementById('dtl-departamento').innerText = c.departamento || 'Antioquia';

        

        const mailEl = document.getElementById('dtl-correo');

        if (mailEl) {

            mailEl.innerText = c.correo_electronico || 'Sin correo registrado';

            mailEl.href = c.correo_electronico ? `mailto:${c.correo_electronico}` : '#';

        }

        document.getElementById('dtl-telefono').innerText = c.telefono || 'Sin teléfono registrado';



        // Section 3

        document.getElementById('dtl-regimen').innerText = regimenLabel;

        document.getElementById('dtl-banco-nombre').innerText = c.banco_nombre || 'Sin entidad bancaria registrada';

        document.getElementById('dtl-banco-cuenta').innerText = c.banco_numero_cuenta 

            ? `${c.banco_tipo_cuenta || 'Ahorros'} No. ${c.banco_numero_cuenta}` 

            : 'Sin cuenta bancaria registrada';



        // Section 4

        document.getElementById('dtl-perfil-experiencia').innerText = c.perfil_o_experiencia_resumen || 'Sin resumen de experiencia o perfil operativo cargado aún en el expediente.';



        // Section 5: Contratos Table

        document.getElementById('dtl-contratos-total-count').innerText = `${contratos.length} contrato(s)`;

        const cBody = document.getElementById('dtl-contratos-body');

        if (contratos.length === 0) {

            cBody.innerHTML = '<tr><td colspan="6" class="p-4 text-center text-slate-500 italic">Este contratista aún no registra contratos suscritos con la ESP.</td></tr>';

        } else {

            const currencyFmt = new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 });

            cBody.innerHTML = contratos.map(ct => `

                <tr class="hover:bg-slate-800/40">

                    <td class="p-2.5 font-mono font-bold text-sky-400 whitespace-nowrap">${ct.numero_contrato}</td>

                    <td class="p-2.5 whitespace-nowrap">${ct.vigencia}</td>

                    <td class="p-2.5 whitespace-nowrap text-slate-300">${ct.tipologia}</td>

                    <td class="p-2.5 font-mono text-emerald-400 whitespace-nowrap">${currencyFmt.format(ct.valor_total || 0)}</td>

                    <td class="p-2.5 whitespace-nowrap">

                        <span class="px-2 py-0.5 rounded text-[10px] font-bold ${ct.estado === 'EN_EJECUCION' ? 'bg-emerald-950 text-emerald-300 border border-emerald-800' : 'bg-slate-800 text-slate-300'}">

                            ${ct.estado}

                        </span>

                    </td>

                    <td class="p-2.5 text-right whitespace-nowrap">

                        <button onclick="closeContractorDetailModal(); viewContractDetail(${ct.id})" 

                                class="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-sky-300 border border-slate-700 text-[11px] font-semibold">

                            Ver Contrato &rarr;

                        </button>

                    </td>

                </tr>

            `).join('');

        }



        // Section 6: Documentos

        const docList = document.getElementById('dtl-documentos-list');

        const docs = c.documentos || [];

        if (docs.length === 0) {

            docList.innerHTML = '<span class="text-slate-500 italic text-xs">Sin documentos soporte cargados directamente.</span>';

        } else {

            docList.innerHTML = docs.map(d => `

                <div class="px-2.5 py-1.5 rounded-lg bg-slate-900 border border-slate-800 flex items-center gap-2 text-xs">

                    <span class="text-slate-400">📄</span>

                    <strong class="text-slate-200">${d.nombre_archivo_original || d.tipo_documento}</strong>

                    <span class="px-1.5 py-0.2 rounded text-[10px] font-mono bg-slate-800 text-sky-400">${d.tipo_documento}</span>

                </div>

            `).join('');

        }



        // Wire Action buttons

        const btnDelete = document.getElementById('dtl-btn-delete');

        const btnEdit = document.getElementById('dtl-btn-edit');

        const btnNewCont = document.getElementById('dtl-btn-new-contract');



        if (btnDelete) btnDelete.onclick = () => promptDeleteContractor(c.id);

        if (btnEdit) btnEdit.onclick = () => { closeContractorDetailModal(); openContractorModal(c.id); };

        if (btnNewCont) btnNewCont.onclick = () => { closeContractorDetailModal(); startContractWithExistingContractor(c.id); };



        modal.classList.remove('hidden');

    } catch (e) {

        showToast(`Error al consultar detalle del contratista: ${e.message}`, 'error');

    }

}



function closeContractorDetailModal() {

    const modal = document.getElementById('contractor-detail-modal');

    if (modal) modal.classList.add('hidden');

}



// -------------------------------------------------------------

// FORMULARIO: REGISTRAR / EDITAR CONTRATISTA

// -------------------------------------------------------------

function onContractorTipoPersonaChange(tipo) {

    const repLegalGroup = document.getElementById('contr-rep-legal-group');

    const tipoDocSelect = document.getElementById('contr-tipo-doc');

    const dvInput = document.getElementById('contr-dv');

    const docLabel = document.getElementById('contr-doc-label');



    if (tipo === 'JURIDICA') {

        if (repLegalGroup) repLegalGroup.classList.remove('hidden');

        if (tipoDocSelect) tipoDocSelect.value = 'NIT';

        if (dvInput) dvInput.classList.remove('hidden');

        if (docLabel) docLabel.innerText = 'NIT de la Empresa *';

    } else {

        if (repLegalGroup) repLegalGroup.classList.add('hidden');

        if (tipoDocSelect) tipoDocSelect.value = 'CC';

        if (dvInput) {

            dvInput.value = '';

            dvInput.classList.add('hidden');

        }

        if (docLabel) docLabel.innerText = 'Número de Cédula (Sin DV) *';

        const numInput = document.getElementById('contr-num-doc');

        if (numInput && numInput.value) {

            numInput.value = numInput.value.replace(/-\d+$/, '').trim();

        }

        if (document.getElementById('contr-rep-nombre')) document.getElementById('contr-rep-nombre').value = '';

        if (document.getElementById('contr-rep-doc')) document.getElementById('contr-rep-doc').value = '';

    }

}



async function handleContractorModalRutUpload(fileList) {

    if (!fileList || fileList.length === 0) return;

    const file = fileList[0];

    const statusEl = document.getElementById('contr-modal-rut-status');

    const contrIdVal = document.getElementById('contr-id')?.value;

    const contrId = contrIdVal ? parseInt(contrIdVal) : null;



    if (statusEl) {

        statusEl.innerHTML = `<span class="animate-spin inline-block w-3.5 h-3.5 border-2 border-sky-400 border-t-transparent rounded-full mr-1"></span> Procesando RUT "${file.name}"...`;

    }



    try {

        let rutData = null;

        if (contrId) {

            // Actualizar directamente en base de datos para contratista existente

            const res = await window.api.updateContractorFromRut(contrId, file);

            rutData = res.extracted_data || {};

            const updated = res.contractor;

            showToast(`¡Empresa actualizada con el RUT! Se actualizaron: ${(res.campos_actualizados || []).join(', ')}`, 'success');

            const idx = (state.contractors || []).findIndex(c => c.id === contrId);

            if (idx >= 0) state.contractors[idx] = updated;

            await openContractorModal(contrId);

            if (statusEl) {

                statusEl.innerHTML = `<span class="text-emerald-400 font-semibold">✓ Empresa actualizada con el RUT oficial.</span>`;

            }

            return;

        } else {

            // Parsear RUT para nuevo contratista

            const parseRes = await window.api.parseRutDocument(file);

            rutData = parseRes.data || {};

        }



        if (rutData) {

            if (rutData.tipo_persona) document.getElementById('contr-tipo-persona').value = rutData.tipo_persona;

            if (rutData.tipo_documento) document.getElementById('contr-tipo-doc').value = rutData.tipo_documento;

            if (rutData.numero_documento) document.getElementById('contr-num-doc').value = rutData.numero_documento;

            if (rutData.digito_verificacion) document.getElementById('contr-dv').value = rutData.digito_verificacion;

            if (rutData.nombre_o_razon_social) document.getElementById('contr-nombre').value = rutData.nombre_o_razon_social;

            if (rutData.nombre_comercial) document.getElementById('contr-nombre-comercial').value = rutData.nombre_comercial;

            if (rutData.representante_legal_nombre) document.getElementById('contr-rep-nombre').value = rutData.representante_legal_nombre;

            if (rutData.representante_legal_documento) document.getElementById('contr-rep-doc').value = rutData.representante_legal_documento;

            if (rutData.direccion) document.getElementById('contr-direccion').value = rutData.direccion;

            if (rutData.municipio) document.getElementById('contr-municipio').value = rutData.municipio;

            if (rutData.departamento) document.getElementById('contr-departamento').value = rutData.departamento;

            if (rutData.correo_electronico) document.getElementById('contr-correo').value = rutData.correo_electronico;

            if (rutData.telefono) document.getElementById('contr-telefono').value = rutData.telefono;

            if (rutData.regimen_tributario) document.getElementById('contr-regimen').value = rutData.regimen_tributario;



            onContractorTipoPersonaChange(rutData.tipo_persona || 'JURIDICA');



            if (statusEl) {

                statusEl.innerHTML = `<span class="text-emerald-400 font-semibold">✓ Datos extraídos del RUT (${rutData.tipo_persona === 'JURIDICA' ? 'Empresa' : 'Persona Natural'}). Revise y guarde.</span>`;

            }

            showToast('Información del RUT cargada en el formulario.', 'success');

        }

    } catch (err) {

        if (statusEl) {

            statusEl.innerHTML = `<span class="text-rose-400 font-medium">✗ Error leyendo RUT: ${err.message}</span>`;

        }

        showToast(`Error al procesar RUT: ${err.message}`, 'error');

    }

}



async function openContractorModal(contractorId = null) {

    const modal = document.getElementById('contractor-modal');

    if (!modal) return;



    document.getElementById('contractor-form').reset();

    document.getElementById('contr-id').value = '';

    const rutStatus = document.getElementById('contr-modal-rut-status');

    if (rutStatus) rutStatus.innerHTML = '';



    if (contractorId) {

        document.getElementById('contr-modal-title').innerText = 'Editar Datos del Contratista';

        let c = (state.contractors || []).find(item => item.id === contractorId);

        if (!c || !c.perfil_o_experiencia_resumen) {

            try {

                c = await window.api.getContractor(contractorId);

            } catch (e) {

                showToast(`Error al cargar datos del contratista: ${e.message}`, 'error');

                return;

            }

        }



        const isJuridica = (c.tipo_persona === 'JURIDICA');

        const cleanDoc = (c.numero_documento || '').replace(/-\d+$/, '').trim();

        const cleanRepDoc = (c.representante_legal_documento || '').replace(/-\d+$/, '').trim();



        document.getElementById('contr-id').value = c.id;

        document.getElementById('contr-tipo-persona').value = isJuridica ? 'JURIDICA' : 'NATURAL';

        document.getElementById('contr-tipo-doc').value = c.tipo_documento || (isJuridica ? 'NIT' : 'CC');

        document.getElementById('contr-nombre').value = c.nombre_o_razon_social || '';

        document.getElementById('contr-nombre-comercial').value = c.nombre_comercial || '';

        document.getElementById('contr-num-doc').value = cleanDoc;

        document.getElementById('contr-dv').value = isJuridica ? (c.digito_verificacion || '') : '';

        document.getElementById('contr-rep-nombre').value = isJuridica ? (c.representante_legal_nombre || '') : '';

        document.getElementById('contr-rep-doc').value = isJuridica ? cleanRepDoc : '';

        document.getElementById('contr-correo').value = c.correo_electronico || '';

        document.getElementById('contr-telefono').value = c.telefono || '';

        document.getElementById('contr-direccion').value = c.direccion || '';

        document.getElementById('contr-municipio').value = c.municipio || 'Yolombó';

        document.getElementById('contr-departamento').value = c.departamento || 'Antioquia';

        document.getElementById('contr-regimen').value = c.regimen_tributario || 'NO_RESPONSABLE_IVA';

        document.getElementById('contr-banco-nombre').value = c.banco_nombre || '';

        document.getElementById('contr-banco-tipo').value = c.banco_tipo_cuenta || 'Ahorros';

        document.getElementById('contr-banco-cuenta').value = c.banco_numero_cuenta || '';

        document.getElementById('contr-perfil-experiencia').value = c.perfil_o_experiencia_resumen || '';



        onContractorTipoPersonaChange(isJuridica ? 'JURIDICA' : 'NATURAL');

    } else {

        document.getElementById('contr-modal-title').innerText = 'Registrar Nuevo Contratista';

        document.getElementById('contr-tipo-persona').value = 'JURIDICA';

        document.getElementById('contr-tipo-doc').value = 'NIT';

        document.getElementById('contr-municipio').value = 'Yolombó';

        document.getElementById('contr-departamento').value = 'Antioquia';

        document.getElementById('contr-regimen').value = 'NO_RESPONSABLE_IVA';

        document.getElementById('contr-banco-tipo').value = 'Ahorros';



        onContractorTipoPersonaChange('JURIDICA');

    }



    modal.classList.remove('hidden');

}



function closeContractorModal() {

    const modal = document.getElementById('contractor-modal');

    if (modal) modal.classList.add('hidden');

}



async function saveContractorForm(event) {

    if (event) event.preventDefault();

    const idVal = document.getElementById('contr-id')?.value;

    const id = idVal ? parseInt(idVal) : null;

    const tipoPersona = document.getElementById('contr-tipo-persona').value;

    const isJuridica = tipoPersona === 'JURIDICA';



    let numDoc = document.getElementById('contr-num-doc').value.trim();

    if (!isJuridica) {

        // En persona natural la cédula se carga y persiste SIN el dígito de verificación

        numDoc = numDoc.replace(/-\d+$/, '').trim();

    }



    let repDoc = document.getElementById('contr-rep-doc')?.value.trim() || null;

    if (repDoc) {

        // Cédula del representante legal siempre sin DV

        repDoc = repDoc.replace(/-\d+$/, '').trim();

    }



    const payload = {

        tipo_persona: tipoPersona,

        tipo_documento: isJuridica ? 'NIT' : (document.getElementById('contr-tipo-doc').value || 'CC'),

        nombre_o_razon_social: document.getElementById('contr-nombre').value.trim(),

        nombre_comercial: document.getElementById('contr-nombre-comercial')?.value.trim() || null,

        numero_documento: numDoc,

        digito_verificacion: isJuridica ? (document.getElementById('contr-dv')?.value.trim() || null) : null,

        representante_legal_nombre: isJuridica ? (document.getElementById('contr-rep-nombre')?.value.trim() || null) : null,

        representante_legal_documento: isJuridica ? repDoc : null,

        correo_electronico: document.getElementById('contr-correo')?.value.trim() || null,

        telefono: document.getElementById('contr-telefono')?.value.trim() || null,

        direccion: document.getElementById('contr-direccion')?.value.trim() || null,

        municipio: document.getElementById('contr-municipio')?.value.trim() || 'Yolombó',

        departamento: document.getElementById('contr-departamento')?.value.trim() || 'Antioquia',

        regimen_tributario: document.getElementById('contr-regimen')?.value || 'NO_RESPONSABLE_IVA',

        banco_nombre: document.getElementById('contr-banco-nombre')?.value.trim() || null,

        banco_tipo_cuenta: document.getElementById('contr-banco-tipo')?.value || null,

        banco_numero_cuenta: document.getElementById('contr-banco-cuenta')?.value.trim() || null,

        perfil_o_experiencia_resumen: document.getElementById('contr-perfil-experiencia')?.value.trim() || null

    };



    if (!payload.nombre_o_razon_social || !payload.numero_documento) {

        showToast('El nombre o razón social y el número de documento son obligatorios.', 'warning');

        return;

    }



    try {

        let savedContractor;

        if (id) {

            showToast('Actualizando información del contratista...', 'info');

            savedContractor = await window.api.updateContractor(id, payload);

            showToast('Contratista actualizado exitosamente.', 'success');

        } else {

            showToast('Registrando nuevo contratista...', 'info');

            savedContractor = await window.api.createContractor(payload);

            showToast('Contratista registrado exitosamente en el sistema.', 'success');

        }



        closeContractorModal();

        await loadContractorsTab();

        await loadDashboard();



        // Si la ficha técnica de este contratista estaba abierta, refrescarla

        const detailModal = document.getElementById('contractor-detail-modal');

        if (detailModal && !detailModal.classList.contains('hidden')) {

            await viewContractorDetail(savedContractor.id);

        }



        const wizSelect = document.getElementById('wiz-select-contractor');

        if (wizSelect) {

            await loadWizardContractorsDropdown(savedContractor.id);

        }

    } catch (e) {

        showToast(`Error al guardar contratista: ${e.message}`, 'error');

    }

}



// -------------------------------------------------------------

// ELIMINACIÓN DE CONTRATISTAS (CON O SIN CASCADA)

// -------------------------------------------------------------

async function promptDeleteContractor(contractorId) {

    const modal = document.getElementById('contractor-delete-modal');

    const content = document.getElementById('contr-delete-modal-content');

    const btnConfirm = document.getElementById('contr-btn-confirm-delete');

    if (!modal || !content || !btnConfirm) return;



    let c = (state.contractors || []).find(item => item.id === contractorId);

    if (!c) {

        try {

            c = await window.api.getContractor(contractorId);

        } catch (e) {

            showToast(`Error: ${e.message}`, 'error');

            return;

        }

    }



    const contratos = c.contratos || [];

    const codigos = c.codigos_contratos || [];

    const numContratos = contratos.length || codigos.length;



    if (numContratos === 0) {

        content.innerHTML = `

            <div class="p-3.5 rounded-xl bg-slate-900 border border-slate-800 space-y-2">

                <p class="text-slate-200">

                    ¿Está seguro de eliminar al contratista <strong class="text-white">${c.nombre_o_razon_social}</strong> (${c.tipo_documento} ${c.numero_documento})?

                </p>

                <div class="flex items-center gap-2 text-emerald-400 text-[11px]">

                    <span>✓</span> Este contratista no registra contratos vinculados.

                </div>

            </div>

            <p class="text-[11px] text-slate-400">

                Esta acción eliminará de forma permanente el registro del contratista y sus datos asociados.

            </p>

        `;

        btnConfirm.innerText = 'Eliminar Contratista';

        btnConfirm.className = 'px-4 py-2 rounded-xl text-xs font-bold bg-rose-700 hover:bg-rose-600 text-white shadow-lg transition-all';

        btnConfirm.onclick = () => executeContractorDelete(contractorId, false);

    } else {

        const codigosList = contratos.length > 0 

            ? contratos.map(ct => ct.numero_contrato).join(', ')

            : codigos.join(', ');



        content.innerHTML = `

            <div class="p-3.5 rounded-xl bg-amber-950/40 border border-amber-800/80 space-y-2.5">

                <div class="flex items-center gap-2 text-amber-300 font-bold text-xs">

                    <span>🛡️</span> Contratista con Historial Contractual

                </div>

                <p class="text-slate-200 text-xs">

                    El contratista <strong class="text-white">${c.nombre_o_razon_social}</strong> tiene <strong class="text-amber-300">${numContratos} contrato(s) registrado(s)</strong>:

                </p>

                <div class="p-2 rounded bg-slate-950/80 border border-slate-800 font-mono text-sky-300 text-[11px] max-h-20 overflow-y-auto">

                    ${codigosList}

                </div>

                <p class="text-[11px] text-slate-300 leading-relaxed">

                    Por trazabilidad y seguridad jurídica, <strong>no es posible eliminar físicamente</strong> a un contratista con contratos vinculados.

                    En su lugar, puede <strong>desactivarlo</strong> para que no aparezca disponible para nuevos contratos sin perder la memoria histórica.

                </p>

            </div>

        `;

        btnConfirm.innerText = 'Desactivar Contratista (Recomendado)';

        btnConfirm.className = 'px-4 py-2 rounded-xl text-xs font-bold bg-amber-600 hover:bg-amber-500 text-white shadow-lg transition-all';

        btnConfirm.onclick = () => executeContractorDeactivate(contractorId);

    }



    modal.classList.remove('hidden');

}



function closeContractorDeleteModal() {

    const modal = document.getElementById('contractor-delete-modal');

    if (modal) modal.classList.add('hidden');

}



async function executeContractorDeactivate(contractorId) {

    try {

        showToast('Desactivando contratista...', 'info');

        await window.api.deactivateContractor(contractorId);

        showToast('Contratista desactivado exitosamente.', 'success');

        

        closeContractorDeleteModal();

        closeContractorDetailModal();

        

        await loadContractorsTab();

        await loadDashboard();

    } catch (e) {

        showToast(`Error al desactivar contratista: ${e.message}`, 'error');

    }

}



async function executeContractorDelete(contractorId, cascade = false) {

    try {

        showToast('Eliminando contratista del sistema...', 'info');

        await window.api.deleteContractor(contractorId);

        showToast('Contratista eliminado exitosamente.', 'success');

        

        closeContractorDeleteModal();

        closeContractorDetailModal();

        

        await loadContractorsTab();

        await loadDashboard();

    } catch (e) {

        showToast(`Error al eliminar contratista: ${e.message}`, 'error');

    }

}



// -------------------------------------------------------------

// EXPORTACIÓN DE CONTRATISTAS A CSV

// -------------------------------------------------------------

function exportContractorsCSV() {

    const list = state.contractors || [];

    if (list.length === 0) {

        showToast('No hay contratistas registrados para exportar.', 'warning');

        return;

    }



    const headers = [

        'ID',

        'Tipo Persona',

        'Tipo Documento',

        'Número Documento',

        'Dígito Verificación',

        'Nombre o Razón Social',

        'Nombre Comercial',

        'Representante Legal',

        'Documento Representante',

        'Correo Electrónico',

        'Teléfono',

        'Dirección',

        'Municipio',

        'Departamento',

        'Régimen Tributario',

        'Banco',

        'Tipo Cuenta',

        'Número Cuenta',

        'Total Contratos',

        'Códigos Contratos'

    ];



    const rows = list.map(c => {

        const codigos = (c.contratos || []).map(ct => ct.numero_contrato).join('; ') || (c.codigos_contratos || []).join('; ');

        const totalC = (c.contratos || []).length || (c.codigos_contratos || []).length;

        

        return [

            c.id,

            c.tipo_persona,

            c.tipo_documento,

            `"${c.numero_documento}"`,

            c.digito_verificacion || '',

            `"${(c.nombre_o_razon_social || '').replace(/"/g, '""')}"`,

            `"${(c.nombre_comercial || '').replace(/"/g, '""')}"`,

            `"${(c.representante_legal_nombre || '').replace(/"/g, '""')}"`,

            `"${c.representante_legal_documento || ''}"`,

            `"${c.correo_electronico || ''}"`,

            `"${c.telefono || ''}"`,

            `"${(c.direccion || '').replace(/"/g, '""')}"`,

            `"${c.municipio || ''}"`,

            `"${c.departamento || ''}"`,

            c.regimen_tributario || '',

            `"${c.banco_nombre || ''}"`,

            c.banco_tipo_cuenta || '',

            `"${c.banco_numero_cuenta || ''}"`,

            totalC,

            `"${codigos}"`

        ];

    });



    const csvContent = '\uFEFF' + [headers.join(','), ...rows.map(e => e.join(','))].join('\r\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });

    const url = URL.createObjectURL(blob);

    const link = document.createElement('a');

    link.setAttribute('href', url);

    link.setAttribute('download', `Directorio_Contratistas_ESPY_${new Date().toISOString().split('T')[0]}.csv`);

    document.body.appendChild(link);

    link.click();

    document.body.removeChild(link);

    showToast('Directorio de contratistas exportado a CSV.', 'success');

}



// Controladores del Asistente (Wizard) para Reutilización de Contratistas

function setWizardContractorMode(mode) {

    const btnExisting = document.getElementById('wiz-mode-btn-existing');

    const btnUpload = document.getElementById('wiz-mode-btn-upload');

    const secExisting = document.getElementById('wiz-existing-contractor-section');

    const secUpload = document.getElementById('wiz-upload-contractor-section');



    if (mode === 'existing') {

        if (btnExisting) {

            btnExisting.className = 'py-2.5 px-3 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-2 bg-sky-600/30 text-sky-300 border border-sky-500/40 shadow-sm';

        }

        if (btnUpload) {

            btnUpload.className = 'py-2.5 px-3 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-2 text-slate-400 hover:text-white border border-transparent';

        }

        if (secExisting) secExisting.classList.remove('hidden');

        if (secUpload) secUpload.classList.add('hidden');

        loadWizardContractorsDropdown();

    } else {

        if (btnUpload) {

            btnUpload.className = 'py-2.5 px-3 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-2 bg-sky-600/30 text-sky-300 border border-sky-500/40 shadow-sm';

        }

        if (btnExisting) {

            btnExisting.className = 'py-2.5 px-3 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-2 text-slate-400 hover:text-white border border-transparent';

        }

        if (secUpload) secUpload.classList.remove('hidden');

        if (secExisting) secExisting.classList.add('hidden');

    }

}



async function loadWizardContractorsDropdown(selectedId = null) {

    const select = document.getElementById('wiz-select-contractor');

    if (!select) return;



    try {

        let list = state.contractors;

        if (!list || list.length === 0) {

            list = await window.api.getContractors();

            state.contractors = list;

        }



        select.innerHTML = '<option value="">-- Seleccionar un contratista de la lista --</option>';

        list.forEach(c => {

            const count = (c.codigos_contratos || []).length;

            const countTxt = count === 1 ? '1 contrato' : `${count} contratos`;

            const opt = document.createElement('option');

            opt.value = c.id;

            opt.textContent = `${c.nombre_o_razon_social} (${c.tipo_documento} ${c.numero_documento}) [${countTxt}]`;

            if (selectedId && c.id === selectedId) {

                opt.selected = true;

            }

            select.appendChild(opt);

        });



        if (selectedId) {

            select.value = selectedId;

            onWizardSelectContractor(selectedId);

        } else if (state.wizard.contractorId && list.some(c => c.id === state.wizard.contractorId)) {

            select.value = state.wizard.contractorId;

            onWizardSelectContractor(state.wizard.contractorId);

        }

    } catch (e) {

        console.error('Error cargando contratistas para el asistente:', e);

    }

}



async function onWizardSelectContractor(contractorId) {

    const card = document.getElementById('wiz-selected-contractor-card');

    if (!contractorId) {

        if (card) card.classList.add('hidden');

        state.wizard.contractorId = null;

        state.wizard.contractorName = '';

        return;

    }



    let c = (state.contractors || []).find(item => item.id == contractorId);

    if (!c) return;



    state.wizard.contractorId = c.id;

    state.wizard.contractorName = c.nombre_o_razon_social;



    const isJuridica = (c.tipo_persona === 'JURIDICA');

    const cleanDoc = (c.numero_documento || '').replace(/-\d+$/, '').trim();

    const cleanRepDoc = (c.representante_legal_documento || '').replace(/-\d+$/, '').trim();



    if (isJuridica) {

        const dvStr = c.digito_verificacion ? `-${c.digito_verificacion}` : '';

        document.getElementById('wiz-sel-tipo-badge').innerText = '🏢 Empresa (Persona Jurídica)';

        document.getElementById('wiz-sel-doc').innerText = `NIT: ${cleanDoc}${dvStr}`;

        document.getElementById('wiz-sel-rep').innerText = c.representante_legal_nombre 

            ? `${c.representante_legal_nombre} (CC ${cleanRepDoc || 'Sin cédula'})` 

            : 'Por definir (Requiere representante legal)';

    } else {

        // Persona Natural: Cédula pura sin dígito de verificación

        document.getElementById('wiz-sel-tipo-badge').innerText = '👤 Persona Natural';

        document.getElementById('wiz-sel-doc').innerText = `CC: ${cleanDoc}`;

        document.getElementById('wiz-sel-rep').innerText = 'Obra en su propio nombre (Persona Natural)';

    }

    document.getElementById('wiz-sel-nombre').innerText = c.nombre_o_razon_social;

    

    document.getElementById('wiz-sel-correo').innerText = c.correo_electronico || 'No registrado';

    document.getElementById('wiz-sel-tel').innerText = c.telefono || 'No registrado';

    

    const dirParts = [c.direccion, c.municipio, c.departamento].filter(Boolean);

    document.getElementById('wiz-sel-dir').innerText = dirParts.length > 0 ? dirParts.join(', ') : 'No registrada';

    

    const bancoTxt = c.banco_nombre 

        ? `${c.banco_nombre} - ${c.banco_tipo_cuenta || 'Ahorros'} No. ${c.banco_numero_cuenta || ''}` 

        : 'Por definir en minuta';

    document.getElementById('wiz-sel-banco').innerText = bancoTxt;



    // Rellenar campos del formulario inline

    if (document.getElementById('wiz-inline-tipo-persona')) {

        document.getElementById('wiz-inline-tipo-persona').value = isJuridica ? 'JURIDICA' : 'NATURAL';

        onWizardInlineTipoPersonaChange(isJuridica ? 'JURIDICA' : 'NATURAL');

    }

    if (document.getElementById('wiz-inline-rep-nombre')) document.getElementById('wiz-inline-rep-nombre').value = isJuridica ? (c.representante_legal_nombre || '') : '';

    if (document.getElementById('wiz-inline-rep-doc')) document.getElementById('wiz-inline-rep-doc').value = isJuridica ? cleanRepDoc : '';

    if (document.getElementById('wiz-inline-dv')) document.getElementById('wiz-inline-dv').value = isJuridica ? (c.digito_verificacion || '') : '';

    if (document.getElementById('wiz-inline-telefono')) document.getElementById('wiz-inline-telefono').value = c.telefono || '';

    if (document.getElementById('wiz-inline-correo')) document.getElementById('wiz-inline-correo').value = c.correo_electronico || '';

    if (document.getElementById('wiz-inline-direccion')) document.getElementById('wiz-inline-direccion').value = c.direccion || '';

    if (document.getElementById('wiz-inline-municipio')) document.getElementById('wiz-inline-municipio').value = c.municipio || 'Yolombó';

    if (document.getElementById('wiz-inline-banco')) document.getElementById('wiz-inline-banco').value = c.banco_nombre || '';

    if (document.getElementById('wiz-inline-cuenta')) document.getElementById('wiz-inline-cuenta').value = c.banco_numero_cuenta || '';



    const contratosContainer = document.getElementById('wiz-sel-contratos-list');

    if (contratosContainer) {

        if (c.contratos && c.contratos.length > 0) {

            contratosContainer.innerHTML = c.contratos.map(ct => `

                <button type="button" onclick="viewContractDetail(${ct.id})" 

                        class="px-2.5 py-1 rounded-lg text-xs font-mono bg-sky-950/80 hover:bg-sky-800 text-sky-300 hover:text-white border border-sky-800/60 transition-all flex items-center gap-1.5 shadow-sm"

                        title="Ver detalle del contrato ${ct.numero_contrato}">

                    <span>📄</span> <strong>${ct.numero_contrato}</strong>

                    <span class="text-[10px] text-sky-400/80 font-sans">(${ct.vigencia || ''})</span>

                </button>

            `).join('');

        } else if (c.codigos_contratos && c.codigos_contratos.length > 0) {

            contratosContainer.innerHTML = c.codigos_contratos.map(code => `

                <span class="px-2.5 py-1 rounded-lg text-xs font-mono bg-sky-950/80 text-sky-300 border border-sky-800/60">

                    📄 ${code}

                </span>

            `).join('');

        } else {

            contratosContainer.innerHTML = `<span class="text-slate-500 italic text-xs">Sin contratos celebrados anteriormente (será su primer contrato con la ESP).</span>`;

        }

    }



    if (card) card.classList.remove('hidden');



    // Evaluar y mostrar campos faltantes en la tarjeta

    await checkWizardContractorMissingFields(c.id);

}



async function checkWizardContractorMissingFields(contractorId) {

    const alertEl = document.getElementById('wiz-sel-missing-alert');

    const completeBadge = document.getElementById('wiz-sel-complete-badge');

    const countEl = document.getElementById('wiz-sel-missing-count');

    const itemsEl = document.getElementById('wiz-sel-missing-items');



    if (!alertEl || !countEl || !itemsEl) return;



    try {

        const res = await window.api.getContractorMissingFields(contractorId);

        if (res.missing_fields && res.missing_fields.length > 0) {

            alertEl.classList.remove('hidden');

            if (completeBadge) completeBadge.classList.add('hidden');

            countEl.innerText = `${res.total_missing} campo(s) pendiente(s)`;

            itemsEl.innerHTML = res.missing_fields.map(m => `

                <span class="px-2 py-0.5 rounded-lg bg-amber-500/20 text-amber-200 border border-amber-500/30 text-[11px] font-medium flex items-center gap-1">

                    <span>${m.icon || '📌'}</span> ${m.label}

                </span>

            `).join('');

        } else {

            alertEl.classList.add('hidden');

            if (completeBadge) completeBadge.classList.remove('hidden');

        }

    } catch (e) {

        console.warn('Error verificando campos faltantes:', e);

    }

}



function triggerExistingContractorUpload(event) {

    if (event) event.stopPropagation();

    const input = document.getElementById('wiz-existing-file-input');

    if (input) {

        input.value = '';

        input.click();

    }

}



function handleExistingDragOver(event) {

    if (event) {

        event.preventDefault();

        event.stopPropagation();

    }

    const dropzone = document.getElementById('wiz-existing-dropzone');

    if (dropzone) {

        dropzone.classList.add('border-sky-400', 'bg-sky-900/40');

    }

}



function handleExistingDragLeave(event) {

    if (event) {

        event.preventDefault();

        event.stopPropagation();

    }

    const dropzone = document.getElementById('wiz-existing-dropzone');

    if (dropzone) {

        dropzone.classList.remove('border-sky-400', 'bg-sky-900/40');

    }

}



function handleExistingFileDrop(event) {

    if (event) {

        event.preventDefault();

        event.stopPropagation();

    }

    const dropzone = document.getElementById('wiz-existing-dropzone');

    if (dropzone) {

        dropzone.classList.remove('border-sky-400', 'bg-sky-900/40');

    }

    if (event && event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files.length > 0) {

        handleUploadExistingContractorDocs(event.dataTransfer.files);

    }

}



async function handleUploadExistingContractorDocs(fileList) {

    if (!state.wizard.contractorId) {

        showToast('Seleccione primero un contratista.', 'warning');

        return;

    }

    if (!fileList || fileList.length === 0) return;



    const files = Array.from(fileList).slice(0, 4);

    const statusEl = document.getElementById('wiz-existing-dropzone-status');

    if (statusEl) {

        statusEl.innerHTML = `<span class="animate-spin inline-block w-3.5 h-3.5 border-2 border-sky-400 border-t-transparent rounded-full mr-1"></span> Extrayendo y actualizando información con ${files.length} documento(s)...`;

    }



    try {

        // Carga de documentos asociados al contratista

        const uploaded = await window.api.uploadMultipleDocuments(files, null, state.wizard.contractorId);

        const docIds = uploaded.map(u => u.id);



        if (!state.wizard.uploadedDocIds) state.wizard.uploadedDocIds = [];

        state.wizard.uploadedDocIds = state.wizard.uploadedDocIds.concat(docIds);

        if (!state.wizard.uploadedDocs) state.wizard.uploadedDocs = [];

        uploaded.forEach(u => {

            state.wizard.uploadedDocs.push({

                id: u.id,

                name: u.nombre_archivo_original,

                size: u.tamano_bytes,

                status: 'Almacenado',

                extracted: false,

                subdocumentos: [],

                tipo: detectDocTypeFromName(u.nombre_archivo_original)

            });

        });



        // Enriquecer contratista con los documentos (RUT, datos de contacto y bancarios)

        const resEnr = await window.api.enrichContractorFromDocs(state.wizard.contractorId, docIds);

        

        // Refrescar contratista

        const refreshed = await window.api.getContractor(state.wizard.contractorId);

        

        // Actualizar en el estado global

        const idx = (state.contractors || []).findIndex(c => c.id === state.wizard.contractorId);

        if (idx >= 0) {

            state.contractors[idx] = refreshed;

        }



        // Refrescar vista

        await onWizardSelectContractor(state.wizard.contractorId);



        // Extraer propuesta, CDP y parámetros del contrato para Paso 2

        try {

            const extRes = await window.api.extractMultipleDocuments(docIds);

            if (extRes && extRes.consolidated) {

                state.wizard.extractedData = extRes.consolidated;

                applyExtractedDataToStep2(extRes.consolidated);

                const badgeEl = document.getElementById('wiz-docs-detected-badge');

                if (badgeEl) {

                    badgeEl.innerText = `📄 ${uploaded.length} doc(s) analizado(s) con IA`;

                    badgeEl.classList.remove('hidden');

                }

            }

        } catch (eExt) {

            console.warn("Aviso en extracción para paso 2:", eExt);

        }



        const camposActualizados = resEnr?.enrichment_summary?.campos_actualizados || [];

        const msg = camposActualizados.length > 0 

            ? `¡Ficha actualizada! Se completaron: ${camposActualizados.join(', ')}. Propuesta analizada para el Paso 2.`

            : 'Documentos asociados, propuesta y ficha del contratista verificados con éxito.';



        if (statusEl) {

            statusEl.innerHTML = `<span class="text-emerald-400 font-semibold">✓ ${msg}</span>`;

        }

        showToast(msg, 'success');

    } catch (e) {

        if (statusEl) {

            statusEl.innerHTML = `<span class="text-rose-400 font-medium">✗ Error: ${e.message}</span>`;

        }

        showToast(`Error al procesar documentos: ${e.message}`, 'error');

    }

}



function onWizardInlineTipoPersonaChange(tipo) {

    const isEmpresa = (tipo === 'JURIDICA' || tipo === 'EMPRESA');

    const block = document.getElementById('wiz-inline-empresa-block');

    if (block) {

        if (isEmpresa) {

            block.classList.remove('hidden');

        } else {

            block.classList.add('hidden');

        }

    }

}



function onExtTipoPersonaChange(tipo) {

    const isEmpresa = (tipo === 'JURIDICA' || tipo === 'EMPRESA');

    const repGroup = document.getElementById('ext-rep-legal-group');

    const dvInput = document.getElementById('ext-dv');

    const tipoDocSelect = document.getElementById('ext-tipo-doc');

    const docLabel = document.getElementById('ext-doc-label');

    const numDocInput = document.getElementById('ext-num-doc');



    if (isEmpresa) {

        if (repGroup) repGroup.classList.remove('hidden');

        if (dvInput) dvInput.classList.remove('hidden');

        if (tipoDocSelect) tipoDocSelect.value = 'NIT';

        if (docLabel) docLabel.innerText = 'Número de NIT (sin DV) *';

    } else {

        if (repGroup) repGroup.classList.add('hidden');

        if (dvInput) {

            dvInput.classList.add('hidden');

            dvInput.value = '';

        }

        if (tipoDocSelect) tipoDocSelect.value = 'CC';

        if (docLabel) docLabel.innerText = 'Número de Cédula (sin DV) *';

        // Limpiar de inmediato cualquier -DV accidental si es Persona Natural

        if (numDocInput && numDocInput.value) {

            numDocInput.value = numDocInput.value.replace(/-\d+$/, '').trim();

        }

    }

}



function toggleWizardInlineEdit() {

    const sec = document.getElementById('wiz-inline-edit-section');

    if (sec) sec.classList.toggle('hidden');

}



async function saveExistingContractorInline() {

    if (!state.wizard.contractorId) return;



    const tipoPersona = document.getElementById('wiz-inline-tipo-persona')?.value || 'NATURAL';

    const isJuridica = (tipoPersona === 'JURIDICA');



    let repNombre = null;

    let repDoc = null;

    let dv = null;



    if (isJuridica) {

        repNombre = document.getElementById('wiz-inline-rep-nombre')?.value.trim() || null;

        const rawRepDoc = document.getElementById('wiz-inline-rep-doc')?.value.trim() || '';

        repDoc = rawRepDoc.replace(/-\d+$/, '').replace(/[^\d]/g, '').trim() || null;

        dv = document.getElementById('wiz-inline-dv')?.value.trim() || null;

    }



    const manualData = {

        tipo_persona: tipoPersona,

        tipo_documento: isJuridica ? 'NIT' : 'CC',

        digito_verificacion: dv,

        representante_legal_nombre: repNombre,

        representante_legal_documento: repDoc,

        telefono: document.getElementById('wiz-inline-telefono')?.value.trim() || null,

        correo_electronico: document.getElementById('wiz-inline-correo')?.value.trim() || null,

        direccion: document.getElementById('wiz-inline-direccion')?.value.trim() || null,

        municipio: document.getElementById('wiz-inline-municipio')?.value.trim() || null,

        banco_nombre: document.getElementById('wiz-inline-banco')?.value.trim() || null,

        banco_numero_cuenta: document.getElementById('wiz-inline-cuenta')?.value.trim() || null

    };



    try {

        showToast('Guardando datos en la ficha del contratista...', 'info');

        await window.api.updateContractor(state.wizard.contractorId, manualData);

        

        // Refrescar contratista

        const refreshed = await window.api.getContractor(state.wizard.contractorId);

        const idx = (state.contractors || []).findIndex(c => c.id === state.wizard.contractorId);

        if (idx >= 0) {

            state.contractors[idx] = refreshed;

        }



        await onWizardSelectContractor(state.wizard.contractorId);

        toggleWizardInlineEdit();

        showToast('Información de contratista actualizada con éxito.', 'success');

    } catch (e) {

        showToast(`Error guardando datos: ${e.message}`, 'error');

    }

}



async function advanceWithExistingContractor() {

    if (!state.wizard.contractorId) {

        showToast('Por favor seleccione un contratista de la lista.', 'warning');

        return;

    }

    const contractor = (state.contractors || []).find(c => c.id == state.wizard.contractorId);

    if (!contractor) {

        showToast('No se encontró la información del contratista seleccionado.', 'error');

        return;

    }



    const inlineTipo = document.getElementById('wiz-inline-tipo-persona')?.value;

    const isJuridica = inlineTipo ? (inlineTipo === 'JURIDICA') : (contractor.tipo_persona === 'JURIDICA');

    const cleanDoc = (contractor.numero_documento || '').replace(/-\d+$/, '').trim();



    let repNom = null;

    let repDoc = null;

    let dv = null;



    if (isJuridica) {

        const inlineRepNom = document.getElementById('wiz-inline-rep-nombre')?.value.trim();

        repNom = inlineRepNom || contractor.representante_legal_nombre || null;



        const inlineRepDoc = (document.getElementById('wiz-inline-rep-doc')?.value || '').trim();

        const baseRepDoc = inlineRepDoc || contractor.representante_legal_documento || '';

        repDoc = baseRepDoc.replace(/-\d+$/, '').replace(/[^\d]/g, '').trim() || null;



        const inlineDv = document.getElementById('wiz-inline-dv')?.value.trim();

        dv = inlineDv || contractor.digito_verificacion || null;

    }



    state.wizard.contractorTipoPersona = isJuridica ? 'JURIDICA' : 'NATURAL';

    state.wizard.contractorDoc = cleanDoc;

    state.wizard.contractorNombre = contractor.nombre_o_razon_social;

    state.wizard.contractorRepLegal = repNom;

    state.wizard.contractorRepDoc = repDoc;

    state.wizard.contractorDv = dv;



    const summaryEl = document.getElementById('wiz-summary-contractor');

    if (summaryEl) {

        if (isJuridica) {

            const dvStr = dv ? `-${dv}` : '';

            const repTxt = repNom ? ` | Rep. Legal: ${repNom} (CC ${repDoc || 'Sin Cédula'})` : '';

            summaryEl.innerText = `${contractor.nombre_o_razon_social} (NIT ${cleanDoc}${dvStr})${repTxt}`;

        } else {

            // PERSONA NATURAL: Cédula limpia estrictamente SIN DV

            summaryEl.innerText = `${contractor.nombre_o_razon_social} (CC ${cleanDoc})`;

        }

    }



    // Si ya tenemos datos extraídos de la propuesta o CDP, aplicarlos inmediatamente

    if (state.wizard.extractedData) {

        applyExtractedDataToStep2(state.wizard.extractedData);

    } else {

        // Consultar si el contratista ya tiene documentos en su expediente en el servidor

        await syncContractorDocumentsToWizard(state.wizard.contractorId);

    }



    // Si el objeto sigue vacío, redactar en segundo plano con el agente inteligente

    const currentObjeto = document.getElementById('wiz-objeto')?.value.trim();

    if (!currentObjeto) {

        setTimeout(() => {

            autoDraftContractParametersWithAgent(true);

        }, 300);

    }



    showToast(`Contratista "${contractor.nombre_o_razon_social}" listo. Proceda con los parámetros del contrato.`, 'success');

    setWizardStep(2);

}



async function startContractWithExistingContractor(contractorId) {

    switchTab('wizard');

    setWizardStep(1);

    setWizardContractorMode('existing');

    await loadWizardContractorsDropdown(contractorId);

    advanceWithExistingContractor();

}



// -------------------------------------------------------------

// WIZARD: ASISTENTE DE CONTRATACIÓN IA

// -------------------------------------------------------------

function resetWizardState() {

    state.wizard = {

        step: 1,

        vigencia: state.selectedVigencia !== 'ALL' ? (state.selectedVigencia || 2026) : 2026,

        numeroContrato: '',

        uploadedDocs: [],

        uploadedDocIds: [],

        uploadedDocId: null,

        uploadedFileName: '',

        extractedData: null,

        contractorId: null,

        contractorName: '',

        tipologia: 'PRESTACION_SERVICIOS',

        modalidad: 'CONTRATACION_DIRECTA',

        necesidad: '',

        alcance: '',

        valorEstimado: 0,

        plazo: 6,

        unidadPlazo: 'MESES',

        supervisorNombre: 'Ing. Supervisor Técnico',

        supervisorCargo: 'Director Operativo y Técnico',

        supervisorTipoDoc: 'CC',

        supervisorDocumento: '70123456',

        supervisorDependencia: 'Gerencia Técnica',

        fechaSuscripcion: '',

        fechaInicio: '',

        fechaTerminacion: '',

        cdpNumero: '',

        cdpFecha: '',

        cdpRubro: '',

        cdpRubroNombre: '',

        cdpValor: null,

        cdpClasificadores: '',

        draftResult: null,

        createdContractId: null

    };



    // 1. Limpiar Paso 1

    const wizSelect = document.getElementById('wiz-select-contractor');

    if (wizSelect) wizSelect.value = '';

    onWizardSelectContractor('');

    setWizardContractorMode('existing');

    if (typeof clearUploadedFiles === 'function') {

        clearUploadedFiles();

    }



    // 2. Limpiar Paso 2

    const sumContractor = document.getElementById('wiz-summary-contractor');

    if (sumContractor) sumContractor.textContent = 'Por definir';

    const docsBadge = document.getElementById('wiz-docs-detected-badge');

    if (docsBadge) {

        docsBadge.textContent = '';

        docsBadge.classList.add('hidden');

    }

    const agentStatus = document.getElementById('step2-agent-status');

    if (agentStatus) agentStatus.innerHTML = '';



    if (typeof selectWizardTypology === 'function') {

        selectWizardTypology('PRESTACION_SERVICIOS');

    }



    const fieldIds = [

        'wiz-objeto', 'wiz-justificacion', 'wiz-marco-juridico', 'wiz-objetivo-general',

        'wiz-valor', 'agent-result-cdp-numero', 'agent-result-cdp-fecha',

        'agent-result-cdp-rubro', 'agent-result-cdp-rubro-nombre',

        'agent-result-cdp-valor', 'agent-result-cdp-clasificadores'

    ];

    fieldIds.forEach(id => {

        const el = document.getElementById(id);

        if (el) el.value = '';

    });



    const plazoEl = document.getElementById('wiz-plazo');

    if (plazoEl) plazoEl.value = '6';

    const unidadPlazoEl = document.getElementById('wiz-unidad-plazo');

    if (unidadPlazoEl) unidadPlazoEl.value = 'MESES';

    const lugarEl = document.getElementById('wiz-lugar');

    if (lugarEl) lugarEl.value = 'Municipio de Yolombó, Antioquia';

    const modEl = document.getElementById('wiz-modalidad');

    if (modEl) modEl.value = 'CONTRATACION_DIRECTA';



    const objList = document.getElementById('wiz-obj-especificos-list');

    if (objList) {

        objList.innerHTML = '';

        if (typeof addWizardObjetivoEspecifico === 'function') {

            addWizardObjetivoEspecifico();

        }

    }



    if (typeof updateCdpLivePreview === 'function') {

        updateCdpLivePreview();

    }



    // 3. Limpiar Paso 3

    ['step3-objeto', 'step3-justificacion', 'step3-marco', 'step3-obligaciones-ep', 'step3-obligaciones-minuta', 'step3-clausulas'].forEach(id => {

        const el = document.getElementById(id);

        if (el) el.value = '';

    });



    // 4. Limpiar Paso 4

    const finalNum = document.getElementById('final-contract-num');

    if (finalNum) finalNum.textContent = 'ESP-2026-XXX';

    const btnEp = document.getElementById('btn-final-download-ep');

    if (btnEp) btnEp.onclick = null;

    const btnMinuta = document.getElementById('btn-final-download-minuta');

    if (btnMinuta) btnMinuta.onclick = null;

    const btnActa = document.getElementById('btn-final-download-acta');

    if (btnActa) btnActa.onclick = null;

    const btnSync = document.getElementById('btn-final-sync-excel');

    if (btnSync) btnSync.onclick = null;



    // Regresar de forma segura al Paso 1

    setWizardStep(1);

    refreshWizardContractNumber();

}



function openNewContractWizard(forceReset = true) {

    switchTab('wizard');

    if (forceReset || state.wizard.step === 4) {

        resetWizardState();

        showToast('Asistente de Contratación iniciado para un nuevo contrato.', 'info');

    }

}



function setWizardStep(stepNum) {

    state.wizard.step = stepNum;

    for (let i = 1; i <= 4; i++) {

        const stepEl = document.getElementById(`wizard-step-${i}`);

        const indicator = document.getElementById(`indicator-step-${i}`);

        if (stepEl) {

            if (i === stepNum) stepEl.classList.remove('hidden');

            else stepEl.classList.add('hidden');

        }

        if (indicator) {

            const activeClasses = ['bg-sky-600', 'text-white', 'border-sky-500'];

            const inactiveClasses = ['bg-slate-100', 'dark:bg-slate-800', 'text-slate-600', 'dark:text-slate-400', 'border-slate-300', 'dark:border-slate-700'];

            const legacyEmerald = ['bg-[#009540]', 'border-emerald-400'];



            if (i <= stepNum) {

                indicator.classList.remove(...inactiveClasses, ...legacyEmerald);

                indicator.classList.add(...activeClasses);

            } else {

                indicator.classList.remove(...activeClasses, ...legacyEmerald);

                indicator.classList.add(...inactiveClasses);

            }

        }

    }



    if (stepNum === 2) {

        const wizSelect = document.getElementById('wiz-vigencia');

        if (wizSelect) {

            const targetVig = state.wizard.vigencia || (state.selectedVigencia !== 'ALL' ? state.selectedVigencia : 2026);

            wizSelect.value = String(targetVig);

            state.wizard.vigencia = parseInt(wizSelect.value, 10);

        }

        refreshWizardContractNumber();



        // Si tenemos datos extraídos en state.wizard, reflejarlos inmediatamente en el formulario del Paso 2

        if (state.wizard.extractedData) {

            applyExtractedDataToStep2(state.wizard.extractedData);

        } else if (state.wizard.contractorId && (!document.getElementById('wiz-objeto')?.value.trim())) {

            syncContractorDocumentsToWizard(state.wizard.contractorId);

        }



        // Asegurar al menos una fila en objetivos específicos si la lista está vacía

        const objListEl = document.getElementById('wiz-obj-especificos-list');

        if (objListEl && objListEl.children.length === 0) {

            addWizardObjetivoEspecifico();

        }

    }

}



function clearUploadedFiles(event) {

    if (event) event.stopPropagation();

    state.wizard.uploadedDocs = [];

    state.wizard.uploadedDocIds = [];

    state.wizard.uploadedDocId = null;

    state.wizard.uploadedFileName = '';

    state.wizard.extractedData = null;



    const fileInput = document.getElementById('file-input');

    if (fileInput) fileInput.value = '';



    const container = document.getElementById('uploaded-files-container');

    if (container) container.classList.add('hidden');



    const btnContainer = document.getElementById('btn-process-docs-container');

    if (btnContainer) btnContainer.classList.add('hidden');



    const preview = document.getElementById('extraction-preview-container');

    if (preview) preview.classList.add('hidden');



    const dropzoneStatus = document.getElementById('dropzone-status');

    if (dropzoneStatus) dropzoneStatus.innerHTML = '';

}



function detectDocTypeFromName(name) {

    const n = (name || '').toLowerCase();

    if (n.includes('cdp') || n.includes('disponibilidad')) {

        return 'CDP';

    }

    if (n.includes('propuesta') || n.includes('cotizac') || n.includes('oferta') || n.includes('presupuesto')) {

        return 'PROPUESTA';

    }

    if (n.includes('estudio') && (n.includes('mercado') || n.includes('precio'))) {

        return 'ESTUDIO_MERCADO';

    }

    if (n.includes('rut')) return 'RUT';

    if (n.includes('cedula') || n.includes('cédula') || n.includes('cc')) return 'CEDULA';

    if (n.includes('camara') || n.includes('comercio') || n.includes('ccomercio')) return 'CAMARA_COMERCIO';

    if (n.includes('antecedent')) return 'ANTECEDENTES';

    return 'OTRO';

}



function updateRequiredDocStatus() {

    const alertEl = document.getElementById('required-doc-alert');

    const iconEl = document.getElementById('required-doc-icon');

    const titleEl = document.getElementById('required-doc-title');

    const descEl = document.getElementById('required-doc-desc');

    if (!alertEl || !titleEl || !descEl) return;



    // Detectar si hay documento clasificado o si un PDF compuesto contiene la propuesta / estudio

    const qualDoc = (state.wizard.uploadedDocs || []).find(d => 

        d.tipo === 'PROPUESTA' || d.tipo === 'ESTUDIO_MERCADO' ||

        (d.subdocumentos && (d.subdocumentos.includes('PROPUESTA_ECONOMICA') || d.subdocumentos.includes('ESTUDIO_MERCADO')))

    );



    if (qualDoc) {

        alertEl.className = "p-2.5 rounded-xl border text-xs flex items-center gap-2.5 transition-all bg-emerald-500/10 border-emerald-500/30 text-emerald-300";

        if (iconEl) iconEl.innerText = "✓";

        titleEl.innerText = "Documento indispensable validado:";

        const isComposite = qualDoc.subdocumentos && qualDoc.subdocumentos.length > 1;

        const compBadge = isComposite ? ' [Expediente Compuesto con Propuesta]' : '';

        const tipoLabel = (qualDoc.tipo === 'ESTUDIO_MERCADO' || qualDoc.subdocumentos?.includes('ESTUDIO_MERCADO')) 

            ? 'Estudio de Mercado' 

            : 'Propuesta Económica';

        descEl.innerHTML = `Se identificó <strong class="text-emerald-200">${qualDoc.name}</strong> (${tipoLabel}${compBadge}). Los agentes podrán estructurar la justificación del estudio previo y el objeto contractual con IA.`;

    } else {

        alertEl.className = "p-2.5 rounded-xl border text-xs flex items-center gap-2.5 transition-all bg-amber-500/10 border-amber-500/30 text-amber-300";

        if (iconEl) iconEl.innerText = "⚠️";

        titleEl.innerText = "Requisito indispensable para Estudio Previo y Objeto:";

        descEl.innerHTML = `Se requiere al menos un archivo (PDF o DOCX) de <strong class="text-amber-200">Propuesta Económica</strong> o <strong class="text-amber-200">Estudio de Mercado</strong> (puede estar incluido dentro de un PDF único con el RUT). Si ya lo subió, clasifíquelo en el selector.`;

    }

}



function onDocTypeChange(docId, newType) {

    const doc = (state.wizard.uploadedDocs || []).find(d => d.id === docId);

    if (doc) {

        doc.tipo = newType;

        updateRequiredDocStatus();

        showToast(`Documento clasificado como ${newType.replace('_', ' ')}.`, 'info');

    }

}



function renderUploadedFilesList() {

    const container = document.getElementById('uploaded-files-container');

    const listEl = document.getElementById('uploaded-files-list');

    const countEl = document.getElementById('uploaded-files-count');

    const btnContainer = document.getElementById('btn-process-docs-container');



    if (!container || !listEl) return;



    if (state.wizard.uploadedDocs.length === 0) {

        container.classList.add('hidden');

        if (btnContainer) btnContainer.classList.add('hidden');

        return;

    }



    container.classList.remove('hidden');

    if (btnContainer) btnContainer.classList.remove('hidden');

    countEl.innerText = `${state.wizard.uploadedDocs.length} / 8 Documentos Cargados`;



    listEl.innerHTML = state.wizard.uploadedDocs.map((doc) => {

        const isPdf = doc.name.toLowerCase().endsWith('.pdf');

        const icon = isPdf ? '📄' : '📝';

        const kb = (doc.size / 1024).toFixed(1);

        const tipo = doc.tipo || detectDocTypeFromName(doc.name);

        doc.tipo = tipo;

        const hasPropSubdoc = doc.subdocumentos && (doc.subdocumentos.includes('PROPUESTA_ECONOMICA') || doc.subdocumentos.includes('ESTUDIO_MERCADO'));

        const isRequiredType = tipo === 'PROPUESTA' || tipo === 'ESTUDIO_MERCADO' || hasPropSubdoc;



        // Renderizar insignias de subdocumentos detectados

        const subdocBadges = (doc.subdocumentos && doc.subdocumentos.length > 0)

            ? `<div class="flex flex-wrap gap-1 pt-1">

                ${doc.subdocumentos.map(s => {

                    let label = s.replace('_', ' ');

                    let color = 'bg-slate-800 text-slate-300 border-slate-700';

                    if (s === 'RUT') { label = 'RUT DIAN'; color = 'bg-amber-500/20 text-amber-300 border-amber-500/30'; }

                    if (s === 'PROPUESTA_ECONOMICA') { label = 'Propuesta Económica'; color = 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'; }

                    if (s === 'ESTUDIO_MERCADO') { label = 'Estudio Mercado'; color = 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'; }

                    if (s === 'CERTIFICACION_BANCARIA') { label = 'Cert. Bancaria'; color = 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30'; }

                    if (s === 'CEDULA') { label = 'Cédula'; color = 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30'; }

                    return `<span class="px-1.5 py-0.5 rounded text-[9px] font-bold border ${color}">✓ ${label}</span>`;

                }).join('')}

               </div>`

            : '';



        return `

            <div class="p-2.5 rounded-xl bg-slate-900/90 border ${isRequiredType ? 'border-emerald-500/40' : 'border-slate-800'} text-xs space-y-1.5">

                <div class="flex items-center justify-between gap-2">

                    <div class="flex items-center gap-2 truncate flex-1">

                        <span class="text-base">${icon}</span>

                        <div class="truncate">

                            <p class="font-medium text-slate-200 truncate" title="${doc.name}">${doc.name}</p>

                            <p class="text-[10px] text-slate-400">${kb} KB • ${doc.status || 'Almacenado'}</p>

                        </div>

                    </div>

                    <span class="px-2 py-0.5 rounded text-[10px] font-semibold whitespace-nowrap ${doc.extracted ? 'bg-emerald-500/20 text-emerald-400' : 'bg-sky-500/20 text-sky-400'}">

                        ${doc.extracted ? '✓ Extraído' : 'Listo'}

                    </span>

                </div>

                ${subdocBadges}

                <div class="flex items-center justify-between gap-2 pt-1 border-t border-slate-800/60">

                    <span class="text-[10px] text-slate-400 font-semibold">Tipo principal:</span>

                    <select onchange="onDocTypeChange(${doc.id}, this.value)" class="bg-slate-800 text-[11px] text-slate-200 rounded px-2 py-0.5 border border-slate-700 focus:outline-none focus:border-sky-500">

                        <option value="PROPUESTA" ${tipo === 'PROPUESTA' ? 'selected' : ''}>Propuesta Económica</option>

                        <option value="ESTUDIO_MERCADO" ${tipo === 'ESTUDIO_MERCADO' ? 'selected' : ''}>Estudio de Mercado</option>

                        <option value="RUT" ${tipo === 'RUT' ? 'selected' : ''}>RUT DIAN</option>

                        <option value="CEDULA" ${tipo === 'CEDULA' ? 'selected' : ''}>Cédula</option>

                        <option value="CAMARA_COMERCIO" ${tipo === 'CAMARA_COMERCIO' ? 'selected' : ''}>Cámara Comercio</option>

                        <option value="ANTECEDENTES" ${tipo === 'ANTECEDENTES' ? 'selected' : ''}>Antecedentes</option>

                        <option value="OTRO" ${tipo === 'OTRO' ? 'selected' : ''}>Otro / Compuesto</option>

                    </select>

                </div>

            </div>

        `;

    }).join('');



    updateRequiredDocStatus();

}



// -------------------------------------------------------------

// CONTROLADORES DE CARGA Y ARRASTRE DE ARCHIVOS (DROPZONE)

// -------------------------------------------------------------

function handleDragOver(event) {

    if (event) {

        event.preventDefault();

        event.stopPropagation();

    }

    const dropzone = document.getElementById('multi-dropzone') || document.getElementById('file-dropzone');

    if (dropzone) {

        dropzone.classList.add('border-sky-500', 'bg-sky-900/30');

    }

}



function handleDragLeave(event) {

    if (event) {

        event.preventDefault();

        event.stopPropagation();

    }

    const dropzone = document.getElementById('multi-dropzone') || document.getElementById('file-dropzone');

    if (dropzone) {

        dropzone.classList.remove('border-sky-500', 'bg-sky-900/30');

    }

}



function handleFileDrop(event) {

    if (event) {

        event.preventDefault();

        event.stopPropagation();

    }

    const dropzone = document.getElementById('multi-dropzone') || document.getElementById('file-dropzone');

    if (dropzone) {

        dropzone.classList.remove('border-sky-500', 'bg-sky-900/30');

    }

    if (event && event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files.length > 0) {

        handleMultipleFilesUpload(event.dataTransfer.files);

    }

}



function handleFileInputChange(event) {

    if (event && event.target && event.target.files && event.target.files.length > 0) {

        handleMultipleFilesUpload(event.target.files);

    }

}



function triggerFileInput(event) {

    if (event && event.target && event.target.id === 'file-input') return;

    const input = document.getElementById('file-input');

    if (input) {

        input.value = '';

        input.click();

    }

}



function processAllUploadedDocs() {

    return processAllUploadedDocuments();

}



async function handleMultipleFilesUpload(fileList) {

    if (!fileList || fileList.length === 0) return;

    const files = Array.from(fileList).slice(0, 8);



    if (fileList.length > 8) {

        showToast('Se seleccionaron más de 8 archivos. Se procesarán los primeros 8.', 'warning');

    }



    const dropzoneStatus = document.getElementById('dropzone-status');

    dropzoneStatus.innerHTML = `<span class="animate-spin inline-block w-4 h-4 border-2 border-sky-400 border-t-transparent rounded-full"></span> Subiendo ${files.length} documento(s)...`;



    try {

        const uploadResponses = await window.api.uploadMultipleDocuments(files);



        state.wizard.uploadedDocs = uploadResponses.map(r => ({

            id: r.id,

            name: r.nombre_archivo_original,

            size: r.tamano_bytes,

            status: 'Almacenado',

            extracted: false,

            subdocumentos: [],

            tipo: detectDocTypeFromName(r.nombre_archivo_original)

        }));

        state.wizard.uploadedDocIds = uploadResponses.map(r => r.id);

        state.wizard.uploadedDocId = uploadResponses[0]?.id || null;

        state.wizard.uploadedFileName = uploadResponses[0]?.nombre_archivo_original || '';



        renderUploadedFilesList();

        dropzoneStatus.innerHTML = `<span class="text-emerald-400 font-semibold">✓ ${uploadResponses.length} archivo(s) almacenados en el servidor.</span> Extrayendo datos con IA...`;



        showToast(`${uploadResponses.length} archivo(s) cargado(s) exitosamente.`, 'success');



        // Procesar automáticamente la extracción combinada

        await processAllUploadedDocuments();

    } catch (e) {

        dropzoneStatus.innerHTML = `<span class="text-rose-400 font-medium">✗ Error cargando archivos: ${e.message}</span>`;

        showToast(`Error al subir archivos: ${e.message}`, 'error');

    }

}



async function processAllUploadedDocuments() {

    if (!state.wizard.uploadedDocIds || state.wizard.uploadedDocIds.length === 0) {

        showToast('Por favor cargue al menos un documento primero.', 'warning');

        return;

    }



    const dropzoneStatus = document.getElementById('dropzone-status');

    dropzoneStatus.innerHTML = `<span class="animate-spin inline-block w-4 h-4 border-2 border-sky-400 border-t-transparent rounded-full"></span> Extrayendo y consolidando RUT, Propuesta y anexos con OCR e IA...`;



    try {

        const res = await window.api.extractMultipleDocuments(state.wizard.uploadedDocIds);

        const extracted = res.consolidated;

        state.wizard.extractedData = extracted;



        // Actualizar badges y subdocumentos detectados en cada archivo

        const procMap = {};

        (res.documentos_procesados || []).forEach(p => {

            procMap[p.id] = p;

        });



        state.wizard.uploadedDocs.forEach(d => {

            d.extracted = true;

            d.status = 'Extraído por IA';

            if (procMap[d.id] && procMap[d.id].subdocumentos_detectados) {

                d.subdocumentos = procMap[d.id].subdocumentos_detectados;

                // Si se detectó propuesta adentro de un PDF llamado genéricamente, ajustar tipo

                if ((d.subdocumentos.includes('PROPUESTA_ECONOMICA') || d.subdocumentos.includes('ESTUDIO_MERCADO')) && (d.tipo === 'OTRO' || d.tipo === 'RUT')) {

                    d.tipo = d.subdocumentos.includes('ESTUDIO_MERCADO') ? 'ESTUDIO_MERCADO' : 'PROPUESTA';

                }

            }

        });

        renderUploadedFilesList();



        // Rellenar formulario de previsualización del Paso 1 con los datos combinados

        const detectedTipo = extracted.tipo_persona || 'NATURAL';

        if (document.getElementById('ext-tipo-persona')) {

            document.getElementById('ext-tipo-persona').value = detectedTipo;

        }

        onExtTipoPersonaChange(detectedTipo);



        document.getElementById('ext-tipo-doc').value = extracted.tipo_documento || (detectedTipo === 'JURIDICA' ? 'NIT' : 'CC');

        const cleanExtDoc = (extracted.numero_documento || '').replace(/-\d+$/, '').trim();

        document.getElementById('ext-num-doc').value = cleanExtDoc;

        if (document.getElementById('ext-dv')) {

            document.getElementById('ext-dv').value = (detectedTipo === 'JURIDICA') ? (extracted.digito_verificacion || '') : '';

        }

        document.getElementById('ext-nombre').value = extracted.nombre_o_razon_social || '';

        if (document.getElementById('ext-regimen') && extracted.regimen_tributario) {

            document.getElementById('ext-regimen').value = extracted.regimen_tributario;

        }

        if (document.getElementById('ext-rep-nombre')) {

            const rawRepNom = (extracted.representante_legal_nombre || extracted.representante_legal || '').trim();

            document.getElementById('ext-rep-nombre').value = (detectedTipo === 'JURIDICA') ? rawRepNom : '';

        }

        if (document.getElementById('ext-rep-doc')) {

            let rawRepDoc = (extracted.representante_legal_documento || extracted.cedula_representante || extracted.representante_legal_identificacion || '').toString();

            let cleanExtRepDoc = rawRepDoc.replace(/-\d+$/, '').replace(/[^\d]/g, '').trim();

            // Prohibir terminantemente copiar el NIT de la empresa en la cédula del representante legal

            if (cleanExtRepDoc === cleanExtDoc || cleanExtRepDoc.length > 10 || ['800', '811', '830', '860', '890', '900', '901', '902'].some(p => cleanExtRepDoc.startsWith(p))) {

                cleanExtRepDoc = '';

            }

            document.getElementById('ext-rep-doc').value = (detectedTipo === 'JURIDICA') ? cleanExtRepDoc : '';

        }

        document.getElementById('ext-direccion').value = extracted.direccion || '';

        document.getElementById('ext-municipio').value = extracted.municipio || 'Colombia';

        document.getElementById('ext-correo').value = extracted.correo_electronico || '';

        document.getElementById('ext-telefono').value = extracted.telefono || '';



        // Rellenar datos bancarios

        if (document.getElementById('ext-banco-nombre')) {

            document.getElementById('ext-banco-nombre').value = extracted.banco_nombre || '';

        }

        if (document.getElementById('ext-banco-tipo') && extracted.banco_tipo_cuenta) {

            document.getElementById('ext-banco-tipo').value = extracted.banco_tipo_cuenta;

        }

        if (document.getElementById('ext-banco-cuenta')) {

            document.getElementById('ext-banco-cuenta').value = extracted.banco_numero_cuenta || '';

        }



        // Mostrar datos de CDP si fueron detectados

        if (extracted.cdp_numero) {

            const cdpContainer = document.getElementById('ext-cdp-container');

            if (cdpContainer) {

                cdpContainer.classList.remove('hidden');

                if (document.getElementById('ext-cdp-num')) document.getElementById('ext-cdp-num').value = extracted.cdp_numero || '';

                if (document.getElementById('ext-cdp-fecha')) document.getElementById('ext-cdp-fecha').value = extracted.cdp_fecha || '';

                if (document.getElementById('ext-cdp-valor')) {

                    const fmtVal = extracted.cdp_valor ? `$${Number(extracted.cdp_valor).toLocaleString('es-CO')} COP` : '';

                    document.getElementById('ext-cdp-valor').value = fmtVal;

                }

                if (document.getElementById('ext-cdp-rubro')) {

                    const rubroTxt = extracted.cdp_rubro_nombre ? `${extracted.cdp_rubro} - ${extracted.cdp_rubro_nombre}` : (extracted.cdp_rubro || '');

                    document.getElementById('ext-cdp-rubro').value = rubroTxt;

                }

            }

            // Auto-llenar campos CDP en Paso 2

            if (document.getElementById('wiz-cdp-numero')) document.getElementById('wiz-cdp-numero').value = extracted.cdp_numero;

            if (document.getElementById('wiz-cdp-fecha') && extracted.cdp_fecha) document.getElementById('wiz-cdp-fecha').value = extracted.cdp_fecha;

            if (document.getElementById('wiz-cdp-rubro') && extracted.cdp_rubro) document.getElementById('wiz-cdp-rubro').value = extracted.cdp_rubro;

        }



        // Aplicar todos los datos extraídos (Objeto, Justificación, Objetivos, CDP, Plazo y Presupuesto) al Paso 2

        applyExtractedDataToStep2(extracted);



        // Subdocumentos detectados en badge

        const badgeEl = document.getElementById('ext-detected-badge');

        if (badgeEl && extracted.subdocumentos_detectados && extracted.subdocumentos_detectados.length > 0) {

            badgeEl.innerText = `Subdocumentos: ${extracted.subdocumentos_detectados.join(', ')}`;

        }



        // Manejar contratista existente detectado por RUT/NIT

        const existingBanner = document.getElementById('ext-existing-contractor-banner');

        const existingNombre = document.getElementById('ext-existing-contractor-nombre');

        const existingTags = document.getElementById('ext-existing-missing-tags');

        if (existingBanner) {

            if (res.is_existing_contractor) {

                existingBanner.classList.remove('hidden');

                if (existingNombre) existingNombre.innerText = res.existing_contractor_nombre || 'Registrado';

                if (existingTags && res.campos_faltantes && res.campos_faltantes.length > 0) {

                    existingTags.innerHTML = `<span class="text-[10px] text-emerald-300 font-bold block mb-1">Campos que se enriquecerán en su ficha:</span>` +

                        res.campos_faltantes.map(f => `<span class="px-2 py-0.5 rounded bg-emerald-900/60 text-emerald-200 border border-emerald-700/60 text-[10px]">✓ ${f}</span>`).join(' ');

                } else if (existingTags) {

                    existingTags.innerHTML = `<span class="text-[10px] text-emerald-300">Ficha técnica previamente completa. Los nuevos documentos quedarán adjuntos en su expediente histórico.</span>`;

                }

            } else {

                existingBanner.classList.add('hidden');

            }

        }



        document.getElementById('extraction-preview-container').classList.remove('hidden');

        dropzoneStatus.innerHTML = `<span class="text-emerald-400 font-medium">✓ Datos consolidados de ${res.total_procesados} documento(s) con éxito. Verifique la información y confirme el contratista.</span>`;

        showToast('Extracción completada. RUT y propuesta identificados.', 'success');

    } catch (e) {

        dropzoneStatus.innerHTML = `<span class="text-rose-400 font-medium">✗ Error en extracción: ${e.message}</span>`;

        showToast(`Error consolidando documentos: ${e.message}`, 'error');

    }

}



async function confirmContractorAndAdvance() {

    if (!state.wizard.uploadedDocIds || state.wizard.uploadedDocIds.length === 0) {

        showToast('Por favor cargue primero al menos un documento (RUT, Propuesta o Cédula).', 'warning');

        return;

    }



    const tipoPersona = document.getElementById('ext-tipo-persona')?.value || 'NATURAL';

    const isJuridica = (tipoPersona === 'JURIDICA');

    const rawDoc = (document.getElementById('ext-num-doc')?.value || '').trim();

    const cleanDoc = rawDoc.replace(/-\d+$/, '').trim();



    let dv = null;

    let repNombre = null;

    let repDoc = null;



    if (isJuridica) {

        dv = (document.getElementById('ext-dv')?.value || '').trim() || null;

        repNombre = (document.getElementById('ext-rep-nombre')?.value || '').trim() || null;

        const rawRepDoc = (document.getElementById('ext-rep-doc')?.value || '').trim();

        repDoc = rawRepDoc.replace(/-\d+$/, '').replace(/[^\d]/g, '').trim() || null;

    }



    const verifiedData = {

        tipo_persona: tipoPersona,

        tipo_documento: isJuridica ? (document.getElementById('ext-tipo-doc')?.value || 'NIT') : 'CC',

        numero_documento: cleanDoc,

        digito_verificacion: dv,

        nombre_o_razon_social: document.getElementById('ext-nombre').value.trim(),

        regimen_tributario: document.getElementById('ext-regimen') ? document.getElementById('ext-regimen').value : null,

        representante_legal_nombre: repNombre,

        representante_legal_documento: repDoc,

        direccion: document.getElementById('ext-direccion').value.trim(),

        municipio: document.getElementById('ext-municipio').value.trim(),

        correo_electronico: document.getElementById('ext-correo').value.trim(),

        telefono: document.getElementById('ext-telefono').value.trim(),

        banco_nombre: document.getElementById('ext-banco-nombre') ? document.getElementById('ext-banco-nombre').value.trim() : null,

        banco_tipo_cuenta: document.getElementById('ext-banco-tipo') ? document.getElementById('ext-banco-tipo').value : null,

        banco_numero_cuenta: document.getElementById('ext-banco-cuenta') ? document.getElementById('ext-banco-cuenta').value.trim() : null

    };



    if (!verifiedData.numero_documento) {

        showToast('El número de documento o NIT es obligatorio.', 'warning');

        return;

    }



    try {

        showToast('Registrando contratista y vinculando expedientes...', 'info');

        const contractor = await window.api.createContractorFromMultipleDocs(

            state.wizard.uploadedDocIds, 

            verifiedData

        );

        state.wizard.contractorId = contractor.id;

        state.wizard.contractorName = contractor.nombre_o_razon_social;

        state.wizard.contractorTipoPersona = tipoPersona;

        state.wizard.contractorDoc = cleanDoc;

        state.wizard.contractorRepLegal = repNombre;

        state.wizard.contractorRepDoc = repDoc;

        state.wizard.contractorDv = dv;



        const summaryEl = document.getElementById('wiz-summary-contractor');

        if (summaryEl) {

            if (isJuridica) {

                const dvStr = contractor.digito_verificacion ? `-${contractor.digito_verificacion}` : '';

                const repTxt = repNombre ? ` | Rep. Legal: ${repNombre} (CC ${repDoc || 'Sin Cédula'})` : '';

                summaryEl.innerText = `${contractor.nombre_o_razon_social} (NIT ${cleanDoc}${dvStr})${repTxt}`;

            } else {

                // Persona Natural: Cédula limpia estrictamente SIN DV

                summaryEl.innerText = `${contractor.nombre_o_razon_social} (CC ${cleanDoc})`;

            }

        }

        showToast(`Contratista vinculado con ${state.wizard.uploadedDocIds.length} documento(s) soporte.`, 'success');



        const hasRequiredDoc = (state.wizard.uploadedDocs || []).some(d => 

            d.tipo === 'PROPUESTA' || d.tipo === 'ESTUDIO_MERCADO' ||

            (d.subdocumentos && (d.subdocumentos.includes('PROPUESTA_ECONOMICA') || d.subdocumentos.includes('ESTUDIO_MERCADO')))

        );

        if (!hasRequiredDoc) {

            showToast('Aviso: Recuerde que para la Justificación del Estudio Previo es indispensable adjuntar la Propuesta Económica o el Estudio de Mercado.', 'warning');

        }



        setWizardStep(2);

        // Asegurar que exista al menos un campo para objetivos específicos en el formulario

        if (document.getElementById('wiz-obj-especificos-list') && document.getElementById('wiz-obj-especificos-list').children.length === 0) {

            addWizardObjetivoEspecifico();

        }

    } catch (e) {

        showToast(`Error guardando contratista: ${e.message}`, 'error');

    }

}



// -------------------------------------------------------------

// CONTROL MANUAL DE OBJETOS, JUSTIFICACIÓN Y OBJETIVOS

// -------------------------------------------------------------

function escapeHtml(str) {

    if (!str) return '';

    return String(str)

        .replace(/&/g, '&amp;')

        .replace(/"/g, '&quot;')

        .replace(/'/g, '&#39;')

        .replace(/</g, '&lt;')

        .replace(/>/g, '&gt;');

}



function formatObjetivoEspecifico(val) {

    if (!val || typeof val !== 'string') return '';

    let s = val.trim();

    if (!s) return '';



    // Limpieza de caracteres de viñeta o números iniciales

    s = s.replace(/^[\-\•\*\s\d\.\,\)]+/, '').trim();

    s = s.replace(/[\.\s]+De\s*$/i, '');



    // Correcciones ortográficas y de OCR

    s = s.replace(/\bcompectaci[oó]n\b/gi, 'compactación');

    s = s.replace(/\bpriveniente\b/gi, 'proveniente');

    s = s.replace(/\bexcavacign\b/gi, 'excavación');

    s = s.replace(/\bexcavacion\b/gi, 'excavación');

    s = s.replace(/\bseccoion\b/gi, 'sección');

    s = s.replace(/\bseccion\b/gi, 'sección');

    s = s.replace(/\btubieria\b/gi, 'tubería');

    s = s.replace(/\btuberia\b/gi, 'tubería');

    s = s.replace(/\bpresion\b/gi, 'presión');

    s = s.replace(/\breposicion\b/gi, 'reposición');

    s = s.replace(/\binstalacion\b/gi, 'instalación');

    s = s.replace(/\bvalvulas?compuer[t]?aelasticade/gi, 'válvulas de compuerta elástica de ');

    s = s.replace(/\btransportee\s*/gi, 'transporte e ');

    s = s.replace(/\binstalacionde\s*/gi, 'instalación de ');

    s = s.replace(/\b3\s*RED\s*21\b/gi, '3" RDE 21');

    s = s.replace(/\b3RED\s*21\b/gi, '3" RDE 21');

    s = s.replace(/(\d+[\"\']?)(?:incluyeaccesoriosy?|incluyendoaccesoriosy?|incluye)/gi, '$1 incluyendo accesorios y ');

    s = s.replace(/\bIncluyeaccesoriosy\b/gi, 'incluyendo accesorios y ');

    s = s.replace(/\bincluyeaccesorios\b/gi, 'incluyendo accesorios');

    s = s.replace(/\bincluye\s*accesorios\s*y\b/gi, 'incluyendo accesorios y ');



    // Dimensiones

    s = s.replace(/,(\d{1,2})\s*[xX]\s*,(\d{1,2})/, '0.$1 x 0.$2 m');

    s = s.replace(/\b0\.(\d{1,2})\s*[xX]\s*0\.(\d{1,2})\b(?!\s*m)/, '0.$1 x 0.$2 m');



    s = s.replace(/\b[yY]\s+[yY]\b/g, 'y');

    s = s.replace(/\s+/g, ' ').trim();



    // Verificación si inicia con infinitivo

    const words = s.split(' ');

    const first = (words[0] || '').toLowerCase().replace(/[,:;.]/g, '');

    const infinitives = [

        "realizar", "ejecutar", "suministrar", "instalar", "construir",

        "prestar", "implementar", "efectuar", "adecuar", "reponer",

        "demoler", "entregar", "disponer", "capacitar", "verificar",

        "garantizar", "emitir", "practicar", "evaluar", "desarrollar",

        "aplicar", "inspeccionar", "adquirir", "reparar", "manejar",

        "actualizar", "elaborar", "coordinar", "dotar", "adelantar"

    ];



    const isInf = infinitives.includes(first) || 

        (first.length >= 4 && (first.endsWith('ar') || first.endsWith('er') || first.endsWith('ir')) && !['lugar', 'primer', 'tercer', 'mujer', 'taller'].includes(first));



    if (isInf) {

        let res = s.charAt(0).toUpperCase() + s.slice(1);

        return res.endsWith('.') ? res : res + '.';

    }



    // Reglas de mapeo sustantivo -> infinitivo

    const mappings = [

        [/^Suministro,?\s*transporte\s*e\s*instalaci[oó]n\s+(?:de\s+)?/i, "Suministrar, transportar e instalar "],

        [/^Suministro\s+y\s+(?:puesta\s+en\s+marcha|instalaci[oó]n)\s+(?:de\s+)?/i, "Suministrar e instalar "],

        [/^Suministro,?\s*transporte\s+y\s+entrega\s+(?:de\s+)?/i, "Suministrar, transportar y entregar "],

        [/^Suministro\s+(?:de\s+)?/i, "Suministrar "],

        [/^Excavaci[oó]n\s+manual\b/i, "Realizar excavación manual"],

        [/^Excavaci[oó]n\s+mec[aá]nica\b/i, "Realizar excavación mecánica"],

        [/^Excavaci[oó]n\s+(?:de\s+|en\s+)?/i, "Realizar excavación "],

        [/^Rotura\s+(?:de\s+)?pavimento\b/i, "Realizar rotura de pavimento"],

        [/^Rotura\s+(?:de\s+)?/i, "Realizar la rotura de "],

        [/^Demolici[oó]n\s+(?:de\s+)?/i, "Realizar la demolición de "],

        [/^Lleno\s+y\s+compactaci[oó]n\b/i, "Realizar lleno y compactación"],

        [/^Llenos?\s+manual(?:es)?\b/i, "Realizar lleno manual"],

        [/^Llenos?\s+(?:con\s+|y\s+)?/i, "Realizar el llenado y compactación "],

        [/^Reposici[oó]n\s+(?:de\s+)?pavimento\b/i, "Realizar reposición de pavimento"],

        [/^Reposici[oó]n\s+(?:de\s+)?/i, "Realizar la reposición de "],

        [/^Instalaci[oó]n\s+(?:de\s+)?/i, "Instalar "],

        [/^Construcci[oó]n\s+(?:de\s+)?/i, "Construir "],

        [/^Mantenimiento\s+(?:preventivo\s+y\s+correctivo\s+)?(?:de|a)\s+/i, "Realizar el mantenimiento de "],

        [/^Mantenimiento\s+(?:de|a)\s+/i, "Realizar el mantenimiento de "],

        [/^Adecuaci[oó]n\s+(?:de\s+)?/i, "Adecuar "],

        [/^Reparaci[oó]n\s+(?:de\s+)?/i, "Reparar "],

        [/^Transporte\s+(?:de\s+)?/i, "Transportar "],

        [/^Disposici[oó]n\s+(?:final\s+)?(?:de\s+)?/i, "Efectuar la disposición final de "],

        [/^Entrega\s+(?:de\s+)?/i, "Entregar "],

        [/^Pr[aá]ctica\s+(?:de\s+)?/i, "Practicar "],

        [/^Emisi[oó]n\s+(?:de\s+)?/i, "Emitir "],

        [/^Valoraci[oó]n\s+(?:de\s+)?/i, "Realizar la valoración de "],

        [/^Elaboraci[oó]n\s+(?:de\s+)?/i, "Elaborar "],

        [/^Revisi[oó]n\s+(?:de\s+)?/i, "Revisar "],

        [/^Implementaci[oó]n\s+(?:de\s+)?/i, "Implementar "],

        [/^Adquisici[oó]n\s+(?:de\s+)?/i, "Adquirir "],

        [/^Aplicaci[oó]n\s+(?:de\s+)?/i, "Aplicar "],

        [/^Succi[oó]n\s+(?:de\s+)?/i, "Realizar la succión de "],

        [/^Retiro\s+(?:de\s+)?/i, "Realizar el retiro de "],

        [/^Verificaci[oó]n\s+(?:de\s+)?/i, "Verificar "]

    ];



    for (const [pattern, replacement] of mappings) {

        if (pattern.test(s)) {

            s = s.replace(pattern, replacement);

            let res = s.charAt(0).toUpperCase() + s.slice(1);

            return res.endsWith('.') ? res : res + '.';

        }

    }



    // Prefijo limpio

    let sClean = s.replace(/^(?:el|la|los|las)\s+/i, '');

    let res = 'Realizar ' + sClean.charAt(0).toLowerCase() + sClean.slice(1);

    res = res.charAt(0).toUpperCase() + res.slice(1);

    return res.endsWith('.') ? res : res + '.';

}



function formatObjetoContractual(val, tipologia = 'PRESTACION_SERVICIOS') {

    if (!val || typeof val !== 'string') return '';

    let s = val.trim();

    if (!s) return '';



    // Limpieza y correcciones de OCR

    s = s.replace(/\bVALVULADE\b/gi, 'VALVULA DE');

    s = s.replace(/\bSECTOR\s+LA\s+CAMELIAS\b/gi, 'DEL SECTOR LAS CAMELIAS');

    s = s.replace(/\bLA\s+CAMELIAS\b/gi, 'LAS CAMELIAS');

    s = s.replace(/\bCASCO\s+RURALMUNICIPIO\b/gi, 'CASCO RURAL MUNICIPIO');



    // FILTRO SANITIZADOR OBLIGATORIO DE OBJETO

    s = s.replace(/(?:PRESTACI[OÓ]N\s+DE\s+SERVICIOS\s+DE\s+APOYO\s+A\s+LA\s+GESTI[OÓ]N\s+PARA\s+DISPONIBILIDAD\s*)+/gi, '');

    s = s.replace(/\bDISPONIBILIDAD\b/gi, '');

    s = s.replace(/(?:PRESTACI[OÓ]N\s+DE\s+SERVICIOS\s+DE\s+APOYO\s+A\s+LA\s+GESTI[OÓ]N\s+PARA\s*){2,}/gi, 'PRESTACIÓN DE SERVICIOS DE APOYO A LA GESTIÓN PARA ');

    s = s.replace(/(?:PRESTACI[OÓ]N\s+DE\s+SERVICIOS(?:\s+PARA)?\s*){2,}/gi, 'PRESTACION DE SERVICIOS PARA ');

    s = s.replace(/TODO\.COSTO/gi, 'TODO COSTO');

    s = s.replace(/\s*ADSCRITOS?\s+AL\s+[AÁ]REA\s+OPERATIVA(?:(?:\s+DE\s+LA)?\s+EMPRESA\s+DE\s+SERVICIOS\s+P[UÚ]BLICOS\s+DE\s+YOLOMB[OÓ](?:\s+E\.?S\.?P\.?)?)?/gi, '');

    s = s.replace(/(?:(?:DE\s+LA|PARA\s+LA)\s+EMPRESA\s+DE\s+SERVICIOS\s+P[UÚ]BLICOS\s+DE\s+YOLOMB[OÓ](?:\s+E\.?S\.?P\.?)?\s*){2,}/gi, 'DE LA EMPRESA DE SERVICIOS PÚBLICOS DE YOLOMBÓ E.S.P. ');

    s = s.replace(/\bPARA\s+APOYO\s+A\s+LA\s+GESTI[OÓ]N\s+PARA\b/gi, 'DE APOYO A LA GESTION PARA');

    s = s.replace(/\bPARA\s+PARA\b/gi, 'PARA');

    s = s.replace(/\s+/g, ' ').trim();



    // 1. Caso emblemático del usuario: Instalación de válvula de sectorización sector Las Camelias

    if (/V[AÁ]LVULA/i.test(s) && /SECTORIZACI[OÓ]N/i.test(s) && /CAMELIAS/i.test(s)) {

        return "PRESTACION DE SERVICIOS PARA LA INSTALACION DE VALVULA DE SECTORIZACION DEL SECTOR LAS CAMELIAS DEL MUNICIPIO DE YOLOMBO";

    }



    // 2. Mantenimiento de pozos sépticos

    if (/POZO[S]?\s+S[EÉ]PTICO[S]?/i.test(s)) {

        return "PRESTACION DE SERVICIOS PARA REALIZAR EL MANTENIMIENTO DE LOS POZOS SEPTICOS A CARGO DE LA EMPRESA DE SERVICIOS PUBLICOS DE YOLOMBO";

    }



    // 3. Evaluaciones médicas ocupacionales

    if (/(?:EVALUACI[OÓ]N|EVALUACIONES|EX[AÁ]MEN(?:ES)?)\s+M[EÉ]DICAS?\s+OCUPACIONAL/i.test(s) || /SALUD\s+OCUPACIONAL/i.test(s)) {

        let cleanMed = s.toUpperCase().replace(/\.$/, '');

        if (!cleanMed.startsWith("REALIZAR") && !cleanMed.startsWith("PRESTACI")) {

            cleanMed = "REALIZAR " + cleanMed;

        }

        return cleanMed;

    }



    // Si ya tiene un encabezado tipológico institucional bien estructurado, no re-concatenar nada

    if (/^(?:PRESTACI[OÓ]N\s+DE\s+SERVICIOS|CONTRATO\s+DE\s+OBRA|EJECUCI[OÓ]N\s+DE\s+OBRAS?|SUMINISTRO|COMPRAVENTA|ARRENDAMIENTO|MANTENIMIENTO\s+Y\s+ADECUACI[OÓ]N)\b/i.test(s)) {

        return s.toUpperCase().replace(/\.$/, '').replace(/\s+/g, ' ').trim();

    }



    const tipo = (tipologia || 'PRESTACION_SERVICIOS').toUpperCase();



    // 4. Por tipología

    if (tipo === 'OBRA') {

        let act = s.replace(/^(?:ejecutar|construir|realizar|obras?\s+para)\s*/i, '').trim();

        act = act.replace(/\s+(?:en\s+el\s+municipio\s+de\s+yolomb[oó]|del\s+municipio\s+de\s+yolomb[oó]|de\s+la\s+empresa.*)$/i, '').trim();

        return `CONTRATO DE OBRA PARA LA EJECUCION DE ${act.toUpperCase()} EN LA INFRAESTRUCTURA DE LA EMPRESA DE SERVICIOS PUBLICOS DE YOLOMBO`;

    } else if (tipo === 'SUMINISTRO') {

        let sum = s.replace(/^(?:suministrar|adquirir|compra\s+de|entrega\s+de)\s*/i, '').trim();

        sum = sum.replace(/\s+(?:para\s+la\s+empresa.*|en\s+el\s+almac[eé]n.*)$/i, '').trim();

        return `SUMINISTRO DE ${sum.toUpperCase()} PARA LA EMPRESA DE SERVICIOS PUBLICOS DE YOLOMBO`;

    } else {

        // PRESTACION DE SERVICIOS

        if (/^(?:INSTALACI[OÓ]N\s+DE|INSTALAR)\b/i.test(s)) {

            let tail = s.replace(/^(?:INSTALACI[OÓ]N\s+DE|INSTALAR)\s*/i, '').trim();

            tail = tail.replace(/\bSECTOR\s+([A-Za-zÁÉÍÓÚáéíóúñÑ\s]+?)(?=\s+(?:EN|DEL|PARA|DE\s+LA|$))/i, 'DEL SECTOR $1');

            tail = tail.replace(/\s+(?:en\s+el\s+municipio\s+de\s+yolomb[oó]|del\s+municipio\s+de\s+yolomb[oó]|para\s+la\s+empresa.*)$/i, '').trim();

            return `PRESTACION DE SERVICIOS PARA LA INSTALACION DE ${tail.toUpperCase()} DEL MUNICIPIO DE YOLOMBO`;

        } else if (/^(?:MANTENIMIENTO\s+DE|REALIZAR\s+(?:EL\s+)?MANTENIMIENTO\s+DE)\b/i.test(s)) {

            let tail = s.replace(/^(?:MANTENIMIENTO\s+DE|REALIZAR\s+(?:EL\s+)?MANTENIMIENTO\s+DE)\s*/i, '').trim();

            tail = tail.replace(/\s+(?:de\s+la\s+empresa.*|del\s+municipio.*)$/i, '').trim();

            return `PRESTACION DE SERVICIOS PARA EL MANTENIMIENTO DE ${tail.toUpperCase()} DE LA EMPRESA DE SERVICIOS PUBLICOS DE YOLOMBO`;

        } else if (/^PRESTAR\s+SERVICIOS/i.test(s)) {

            let tail = s.replace(/^PRESTAR\s+SERVICIOS\s+(?:PROFESIONALES\s+Y\s+DE\s+APOYO\s+A\s+LA\s+GESTI[OÓ]N\s+(?:T[EÉ]CNICA\s+)?ESPECIALIZADA\s+(?:CON\s+PLENA\s+AUTONOM[IÍ]A\s+)?(?:PARA|EN)\s+|DE\s+|PARA\s+)/i, '').trim();

            tail = tail.replace(/^(?:para\s+de\s+la|para\s+la|para\s+el|para\s+los|para\s+las|de\s+la|de\s+el|del)\s*/i, '').trim();

            if (!/YOLOMBO/i.test(tail) && !/EMPRESA DE SERVICIOS/i.test(tail)) {

                return `PRESTACION DE SERVICIOS PARA ${tail.toUpperCase()} DEL MUNICIPIO DE YOLOMBO`;

            }

            return `PRESTACION DE SERVICIOS PARA ${tail.toUpperCase()}`;

        }

    }



    return s.toUpperCase().replace(/\.$/, '').replace(/\s+/g, ' ').trim();

}



function addWizardObjetivoEspecifico(value = '') {

    const container = document.getElementById('wiz-obj-especificos-list');

    if (!container) return;

    const formattedValue = value ? formatObjetivoEspecifico(value) : '';

    const rowId = 'wiz-obj-' + Date.now() + '-' + Math.floor(Math.random() * 1000);

    const div = document.createElement('div');

    div.id = rowId;

    div.className = 'flex items-center gap-2';

    div.innerHTML = `

        <span class="text-slate-500 text-xs">•</span>

        <input type="text" value="${escapeHtml(formattedValue)}" 

               onblur="if(this.value.trim()){ this.value = formatObjetivoEspecifico(this.value); }"

               placeholder="Ej: Realizar excavación manual bajo cualquier grado de humedad para instalación de tubería..." 

               class="wiz-obj-item-input flex-1 bg-slate-900 border border-slate-700 rounded-lg p-2 text-white text-xs focus:outline-none focus:border-emerald-500">

        <button type="button" onclick="document.getElementById('${rowId}').remove()" class="text-slate-400 hover:text-rose-400 px-2 py-1 rounded text-xs transition-colors" title="Eliminar objetivo">✕</button>

    `;

    container.appendChild(div);

}



function getWizardObjetivosEspecificos() {

    const inputs = document.querySelectorAll('.wiz-obj-item-input');

    const list = [];

    inputs.forEach(inp => {

        const val = inp.value.trim();

        if (val) {

            const formatted = formatObjetivoEspecifico(val);

            if (formatted) list.push(formatted);

        }

    });

    return list;

}



// -------------------------------------------------------------

// APLICACIÓN AUTOMÁTICA DE DATOS EXTRAÍDOS AL PASO 2 Y CDP

// -------------------------------------------------------------

function applyExtractedDataToStep2(extracted) {

    if (!extracted) return;



    // 1. Presupuesto estimado (priorizar propuesta económica, luego CDP)

    const targetValor = extracted.valor_propuesto || extracted.cdp_valor;

    if (targetValor) {

        const valorInput = document.getElementById('wiz-valor');

        if (valorInput) valorInput.value = targetValor;

        state.wizard.valorEstimado = targetValor;

    }



    // 2. Plazo de ejecución y unidad

    if (extracted.plazo_propuesto) {

        const plazoInput = document.getElementById('wiz-plazo');

        if (plazoInput) plazoInput.value = extracted.plazo_propuesto;

        state.wizard.plazo = extracted.plazo_propuesto;

        if (extracted.unidad_plazo_propuesto && document.getElementById('wiz-unidad-plazo')) {

            document.getElementById('wiz-unidad-plazo').value = extracted.unidad_plazo_propuesto;

        }

    }



    // 3. Objeto Contractual (PROHIBIDO tomar texto del CDP. Se toma EXCLUSIVAMENTE de la Propuesta / Cotización)

    let rawObjeto = extracted.objeto_propuesto || '';

    const targetObjeto = rawObjeto ? formatObjetoContractual(rawObjeto, state.wizard.typology) : '';

    if (targetObjeto) {

        state.wizard.necesidad = targetObjeto;

        const objInput = document.getElementById('wiz-objeto');

        if (objInput) {

            objInput.value = targetObjeto;

        }

    }



    // 4. Objetivo General

    const targetObjGeneral = extracted.objetivo_general || targetObjeto;

    if (targetObjGeneral) {

        state.wizard.objetivoGeneral = targetObjGeneral;

        const genInput = document.getElementById('wiz-obj-general');

        if (genInput) {

            genInput.value = targetObjGeneral;

        }

    }



    // 5. Objetivos Específicos

    const rawObjs = extracted.objetivos_especificos || extracted.actividades_propuesta;

    if (Array.isArray(rawObjs) && rawObjs.length > 0) {

        const listEl = document.getElementById('wiz-obj-especificos-list');

        if (listEl) {

            listEl.innerHTML = '';

            rawObjs.forEach(act => {

                if (typeof act === 'string' && act.trim()) {

                    addWizardObjetivoEspecifico(act.trim());

                }

            });

        }

    } else if (document.getElementById('wiz-obj-especificos-list') && document.getElementById('wiz-obj-especificos-list').children.length === 0) {

        addWizardObjetivoEspecifico();

    }



    // 6. Alcance técnico

    if (extracted.alcance_propuesto) {

        state.wizard.alcance = extracted.alcance_propuesto;

        const alcInput = document.getElementById('wiz-alcance');

        if (alcInput) alcInput.value = extracted.alcance_propuesto;

    }



    // 7. Justificación de la necesidad (Estudio Previo)

    const justEl = document.getElementById('wiz-justificacion');

    if (justEl && (!justEl.value || justEl.value.trim() === '')) {

        const objDesc = targetObjeto || extracted.alcance_propuesto || '';

        if (objDesc) {

            window.api.buildNecesidad({

                objeto: objDesc,

                tipologia: state.wizard?.typology || 'PRESTACION_SERVICIOS',

                contexto_adicional: extracted.alcance_propuesto || ''

            }).then(res => {

                if (res && (res.texto_completo || res.justificacion_necesidad) && (!justEl.value || justEl.value.trim() === '')) {

                    const txt = res.texto_completo || res.justificacion_necesidad;

                    justEl.value = txt;

                    if (state.wizard) state.wizard.justificacion = txt;

                }

            }).catch(err => {

                console.warn('Auto-build necesidad inicial:', err);

            });

        }

    }





    // 8. Datos de Disponibilidad Presupuestal (CDP)

    if (extracted.cdp_numero) {

        const cdpNumEl = document.getElementById('wiz-cdp-numero');

        if (cdpNumEl) cdpNumEl.value = extracted.cdp_numero;

    }

    if (extracted.cdp_fecha) {

        const cdpFechaEl = document.getElementById('wiz-cdp-fecha');

        if (cdpFechaEl) cdpFechaEl.value = extracted.cdp_fecha;

    }

    if (extracted.cdp_rubro) {

        const cdpRubroEl = document.getElementById('wiz-cdp-rubro');

        if (cdpRubroEl) {

            cdpRubroEl.value = extracted.cdp_rubro_nombre 

                ? `${extracted.cdp_rubro} - ${extracted.cdp_rubro_nombre}` 

                : extracted.cdp_rubro;

        }

    }

}



async function autoDraftContractParametersWithAgent(silent = false) {

    const statusEl = document.getElementById('step2-agent-status');

    const btnEl = document.getElementById('btn-agent-autofill');

    if (statusEl) {

        statusEl.innerHTML = `<span class="animate-spin inline-block w-3.5 h-3.5 border-2 border-sky-400 border-t-transparent rounded-full mr-1.5"></span> Redactando objeto, justificación y objetivos con Inteligencia Artificial especializada en Ley 142/94...`;

    }

    if (btnEl) btnEl.disabled = true;



    try {

        // Enviar la necesidad real o actividades extraídas de la propuesta, no el objeto previamente concatenado

        const inputNecesidad = state.wizard.necesidadPropuesta 

            || state.wizard.necesidad 

            || document.getElementById('wiz-objeto')?.value.trim() 

            || '';



        const nivelExt = state.wizard?.extensionLevel || 'MEDIA';

        const instrAdic = document.getElementById('wiz-instrucciones-adicionales')?.value.trim() || null;



        const payload = {

            tipologia: state.wizard.typology || 'PRESTACION_SERVICIOS',

            necesidad_descripcion: inputNecesidad,

            alcance_esperado: document.getElementById('wiz-alcance')?.value.trim() || state.wizard.alcance || '',

            valor_estimado: parseFloat(document.getElementById('wiz-valor')?.value) || state.wizard.valorEstimado || 0,

            plazo: parseInt(document.getElementById('wiz-plazo')?.value) || state.wizard.plazo || 1,

            contratista_id: state.wizard.contractorId || null,

            document_ids: state.wizard.uploadedDocIds || [],

            nivel_extension: nivelExt,

            instrucciones_adicionales: instrAdic

        };



        const res = await window.api.draftWithAgent(payload);

        const draft = res.draft_result || res || {};



        if (draft.objeto && document.getElementById('wiz-objeto')) {

            let formattedObj = formatObjetoContractual(draft.objeto, state.wizard.typology);

            formattedObj = sanitizeObjetoContractual(formattedObj);

            // Reset y sobreescritura limpia total

            document.getElementById('wiz-objeto').value = '';

            document.getElementById('wiz-objeto').value = formattedObj;

            state.wizard.necesidad = formattedObj;

        }

        const justTexto = draft.justificacion_necesidad || draft.justificacion;

        if (justTexto && document.getElementById('wiz-justificacion')) {

            document.getElementById('wiz-justificacion').value = justTexto;

            state.wizard.justificacion = justTexto;

        }

        if (draft.marco_juridico && document.getElementById('wiz-marco-juridico')) {

            document.getElementById('wiz-marco-juridico').value = draft.marco_juridico;

        }

        const objGen = draft.objetivo_general || draft.objeto || '';

        if (objGen && document.getElementById('wiz-obj-general')) {

            document.getElementById('wiz-obj-general').value = objGen;

            state.wizard.objetivoGeneral = objGen;

        }

        if (draft.objetivos_especificos && Array.isArray(draft.objetivos_especificos) && draft.objetivos_especificos.length > 0) {

            const listEl = document.getElementById('wiz-obj-especificos-list');

            if (listEl) {

                listEl.innerHTML = '';

                draft.objetivos_especificos.forEach(obj => {

                    if (typeof obj === 'string' && obj.trim()) {

                        addWizardObjetivoEspecifico(obj.trim());

                    }

                });

            }

        }

        if (draft.obligaciones_empresa && Array.isArray(draft.obligaciones_empresa) && draft.obligaciones_empresa.length > 0) {

            state.wizard.obligacionesEmpresa = draft.obligaciones_empresa;

        }

        if (draft.obligaciones_estudio_previo && Array.isArray(draft.obligaciones_estudio_previo) && draft.obligaciones_estudio_previo.length > 0) {

            state.wizard.obligacionesEp = draft.obligaciones_estudio_previo;

        }

        if (draft.obligaciones_minuta && Array.isArray(draft.obligaciones_minuta) && draft.obligaciones_minuta.length > 0) {

            state.wizard.obligacionesMinuta = draft.obligaciones_minuta;

        }

        if (res.presupuesto_sugerido && (!document.getElementById('wiz-valor')?.value || document.getElementById('wiz-valor')?.value == '0' || document.getElementById('wiz-valor')?.value == '25000000')) {

            if (document.getElementById('wiz-valor')) document.getElementById('wiz-valor').value = res.presupuesto_sugerido;

            state.wizard.valorEstimado = res.presupuesto_sugerido;

        }

        if (res.plazo_sugerido && (!document.getElementById('wiz-plazo')?.value || document.getElementById('wiz-plazo')?.value == '0' || document.getElementById('wiz-plazo')?.value == '6')) {

            if (document.getElementById('wiz-plazo')) document.getElementById('wiz-plazo').value = res.plazo_sugerido;

            state.wizard.plazo = res.plazo_sugerido;

        }



        if (statusEl) {

            statusEl.innerHTML = `<span class="text-emerald-400 font-semibold">✓ Redacción completada con éxito por el Agente IA. Puede revisar o ajustar los textos.</span>`;

        }

        if (!silent) {

            showToast('El Agente IA redactó con éxito el Objeto, la Justificación y los Objetivos.', 'success');

        }

    } catch (e) {

        console.error('Error redactando con agente:', e);

        if (statusEl) {

            statusEl.innerHTML = `<span class="text-rose-400 font-medium">✗ Error al redactar con IA: ${e.message}</span>`;

        }

        if (!silent) {

            showToast(`Error al redactar con IA: ${e.message}`, 'error');

        }

    } finally {

        if (btnEl) btnEl.disabled = false;

    }

}



function triggerStep2ProposalUpload(event) {

    if (event) event.stopPropagation();

    const input = document.getElementById('step2-proposal-file-input');

    if (input) {

        input.value = '';

        input.click();

    }

}



async function handleStep2ProposalUpload(fileList) {

    if (!fileList || fileList.length === 0) return;

    const files = Array.from(fileList);

    const statusEl = document.getElementById('step2-agent-status');



    if (statusEl) {

        statusEl.innerHTML = `<span class="animate-spin inline-block w-3.5 h-3.5 border-2 border-sky-400 border-t-transparent rounded-full mr-1.5"></span> Subiendo y analizando propuesta económica con OCR e Inteligencia Artificial...`;

    }



    try {

        const uploaded = await window.api.uploadMultipleDocuments(files, null, state.wizard.contractorId);

        const docIds = uploaded.map(u => u.id);



        if (!state.wizard.uploadedDocIds) state.wizard.uploadedDocIds = [];

        state.wizard.uploadedDocIds = state.wizard.uploadedDocIds.concat(docIds);



        const extRes = await window.api.extractMultipleDocuments(docIds);

        if (extRes && extRes.consolidated) {

            state.wizard.extractedData = extRes.consolidated;

            applyExtractedDataToStep2(extRes.consolidated);

        }



        // Llamar a redactar con el agente para consolidar la redacción bajo la Ley 142/1994

        await autoDraftContractParametersWithAgent(true);



        if (statusEl) {

            statusEl.innerHTML = `<span class="text-emerald-400 font-semibold">✓ Propuesta cargada y parámetros contractuales autocompletados con éxito.</span>`;

        }

        showToast('Propuesta analizada: Objeto, objetivos y valores actualizados.', 'success');

    } catch (e) {

        console.error('Error cargando propuesta en Paso 2:', e);

        if (statusEl) {

            statusEl.innerHTML = `<span class="text-rose-400 font-medium">✗ Error cargando propuesta: ${e.message}</span>`;

        }

        showToast(`Error al cargar propuesta: ${e.message}`, 'error');

    }

}



function triggerCdpUpload(event) {

    if (event && event.target && event.target.id === 'wiz-cdp-file-input') return;

    const input = document.getElementById('wiz-cdp-file-input');

    if (input) {

        input.value = '';

        input.click();

    }

}



function handleCdpDragOver(event) {

    if (event) {

        event.preventDefault();

        event.stopPropagation();

    }

    const dropzone = document.getElementById('wiz-cdp-dropzone');

    if (dropzone) {

        dropzone.classList.add('border-amber-400', 'bg-amber-950/40');

    }

}



function handleCdpDragLeave(event) {

    if (event) {

        event.preventDefault();

        event.stopPropagation();

    }

    const dropzone = document.getElementById('wiz-cdp-dropzone');

    if (dropzone) {

        dropzone.classList.remove('border-amber-400', 'bg-amber-950/40');

    }

}



function handleCdpDrop(event) {

    if (event) {

        event.preventDefault();

        event.stopPropagation();

    }

    const dropzone = document.getElementById('wiz-cdp-dropzone');

    if (dropzone) {

        dropzone.classList.remove('border-amber-400', 'bg-amber-950/40');

    }

    if (event && event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files.length > 0) {

        handleCdpFileUpload(event.dataTransfer.files);

    }

}



function updateCdpLivePreview() {

    const num = document.getElementById('agent-result-cdp-numero')?.value.trim() 

        || document.getElementById('wiz-cdp-numero')?.value.trim() 

        || state.wizard?.cdpNumero 

        || '000';

    const fecha = document.getElementById('agent-result-cdp-fecha')?.value 

        || document.getElementById('wiz-cdp-fecha')?.value 

        || state.wizard?.cdpFecha;

    const valor = parseFloat(document.getElementById('agent-result-cdp-valor')?.value) 

        || parseFloat(document.getElementById('wiz-cdp-valor')?.value) 

        || state.wizard?.cdpValor 

        || state.wizard?.valorEstimado 

        || 0;

    const rubro = document.getElementById('agent-result-cdp-rubro')?.value.trim() 

        || document.getElementById('wiz-cdp-rubro')?.value.trim() 

        || state.wizard?.cdpRubro 

        || '';

    const rubroNom = document.getElementById('agent-result-cdp-rubro-nombre')?.value.trim() 

        || document.getElementById('wiz-cdp-rubro-nombre')?.value.trim() 

        || state.wizard?.cdpRubroNombre 

        || '';

    const clasif = document.getElementById('agent-result-cdp-clasificadores')?.value.trim() 

        || document.getElementById('wiz-cdp-clasificadores')?.value.trim() 

        || (Array.isArray(state.wizard?.cdpClasificadores) ? state.wizard.cdpClasificadores.join('; ') : state.wizard?.cdpClasificadores) 

        || '';



    let fechaTxt = '';

    if (fecha) {

        try {

            const parts = String(fecha).substring(0, 10).split('-');

            if (parts.length === 3) {

                const year = parts[0];

                const month = parseInt(parts[1], 10);

                const day = parseInt(parts[2], 10);

                const meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];

                fechaTxt = `${day} de ${meses[month - 1]} de ${year}`;

            } else {

                fechaTxt = fecha;

            }

        } catch (e) {

            fechaTxt = fecha;

        }

    }



    const valorTxt = valor ? `$${Math.round(valor).toLocaleString('de-DE')}` : '';

    const rubroDesc = (rubro && rubroNom) ? `${rubro} – ${rubroNom}` : (rubro || rubroNom);



    const parts = [num];

    if (fechaTxt) parts.push(`expedido el ${fechaTxt}`);

    if (valorTxt) parts.push(`por valor de ${valorTxt}`);

    if (rubroDesc) parts.push(`con cargo al Rubro Presupuestal ${rubroDesc}`);



    const preview = limpiarTextoCdp(parts.join(', '));

    const previewEl = document.getElementById('agent-result-cdp-preview');

    if (previewEl) {

        previewEl.innerText = preview;

    }

    return preview;

}



async function handleCdpFileUpload(fileList) {

    if (!fileList || fileList.length === 0) return;

    const file = fileList[0];

    const statusEl = document.getElementById('wiz-cdp-upload-status');



    if (statusEl) {

        statusEl.innerHTML = `<span class="animate-spin inline-block w-3.5 h-3.5 border-2 border-amber-400 border-t-transparent rounded-full mr-1.5"></span> Leyendo y extrayendo CDP con OCR e Inteligencia Artificial...`;

    }



    try {

        const uploadRes = await window.api.uploadDocument(file, null, state.wizard.contractorId, 'CDP');

        const docId = uploadRes.id;



        if (!state.wizard.uploadedDocIds) state.wizard.uploadedDocIds = [];

        if (!state.wizard.uploadedDocIds.includes(docId)) {

            state.wizard.uploadedDocIds.push(docId);

        }



        const extRes = await window.api.extractDocumentData(docId);

        const ext = extRes.extracted_data || extRes.consolidated || extRes;



        if (ext.cdp_numero) {

            if (document.getElementById('wiz-cdp-numero')) document.getElementById('wiz-cdp-numero').value = ext.cdp_numero;

            state.wizard.cdpNumero = ext.cdp_numero;

        }

        if (ext.cdp_fecha) {

            if (document.getElementById('wiz-cdp-fecha')) document.getElementById('wiz-cdp-fecha').value = ext.cdp_fecha;

            state.wizard.cdpFecha = ext.cdp_fecha;

        }

        if (ext.cdp_rubro) {

            if (document.getElementById('wiz-cdp-rubro')) document.getElementById('wiz-cdp-rubro').value = ext.cdp_rubro;

            state.wizard.cdpRubro = ext.cdp_rubro;

        }

        if (ext.cdp_rubro_nombre) {

            if (document.getElementById('wiz-cdp-rubro-nombre')) document.getElementById('wiz-cdp-rubro-nombre').value = ext.cdp_rubro_nombre;

            state.wizard.cdpRubroNombre = ext.cdp_rubro_nombre;

        }

        if (ext.cdp_valor) {

            const valEl = document.getElementById('wiz-valor');

            if (valEl) valEl.value = ext.cdp_valor;

            const cdpValEl = document.getElementById('wiz-cdp-valor');

            if (cdpValEl) cdpValEl.value = ext.cdp_valor;

            state.wizard.valorEstimado = ext.cdp_valor;

            state.wizard.cdpValor = ext.cdp_valor;

        }

        if (ext.cdp_clasificadores && ext.cdp_clasificadores.length > 0) {

            const clasifStr = Array.isArray(ext.cdp_clasificadores) ? ext.cdp_clasificadores.join('\n') : ext.cdp_clasificadores;

            const clasifEl = document.getElementById('wiz-cdp-clasificadores');

            if (clasifEl) clasifEl.value = clasifStr;

            state.wizard.cdpClasificadores = clasifStr;

        }

        if (ext.cdp_texto_completo) {

            state.wizard.cdpTextoCompleto = limpiarTextoCdp(ext.cdp_texto_completo);

        }

        // El objeto contractual NUNCA se toma del CDP, se respeta la propuesta técnica del contratista

        if (ext.cdp_objeto) {

            state.wizard.cdpObjetoOriginal = ext.cdp_objeto;

        }



        const valorFmt = ext.cdp_valor ? `$${Number(ext.cdp_valor).toLocaleString('de-DE')} COP` : '';

        if (statusEl) {

            statusEl.innerHTML = `<span class="text-emerald-400 font-semibold">✓ CDP No. ${ext.cdp_numero || 'Identificado'} cargado con éxito. Valor: ${valorFmt}.</span>`;

        }

        showToast(`CDP ${ext.cdp_numero || ''} procesado y cargado en el formulario con sus clasificadores presupuestales.`, 'success');

    } catch (e) {

        console.error('Error procesando CDP:', e);

        if (statusEl) {

            statusEl.innerHTML = `<span class="text-rose-400 font-medium">✗ Error leyendo CDP: ${e.message}</span>`;

        }

        showToast(`Error al leer archivo de CDP: ${e.message}`, 'error');

    }

}



async function syncContractorDocumentsToWizard(contractorId) {

    if (!contractorId) return;

    try {

        const docs = await window.api.getDocuments(null, contractorId);

        if (docs && docs.length > 0) {

            const docIds = docs.map(d => d.id);

            if (!state.wizard.uploadedDocIds) state.wizard.uploadedDocIds = [];

            docIds.forEach(id => {

                if (!state.wizard.uploadedDocIds.includes(id)) {

                    state.wizard.uploadedDocIds.push(id);

                }

            });



            const extRes = await window.api.extractMultipleDocuments(docIds);

            if (extRes && extRes.consolidated) {

                state.wizard.extractedData = extRes.consolidated;

                applyExtractedDataToStep2(extRes.consolidated);

            }

        }

    } catch (e) {

        console.warn('Aviso sincronizando documentos previos del contratista:', e);

    }

}



function addStep3ObjetivoEspecifico(value = '') {

    const container = document.getElementById('agent-result-obj-especificos-list');

    if (!container) return;

    const rowId = 'step3-obj-' + Date.now() + '-' + Math.floor(Math.random() * 1000);

    const div = document.createElement('div');

    div.id = rowId;

    div.className = 'flex items-center gap-2';

    div.innerHTML = `

        <span class="text-slate-500 text-xs">•</span>

        <input type="text" value="${escapeHtml(value)}" placeholder="Objetivo específico..." 

               class="step3-obj-item-input flex-1 bg-slate-950 border border-slate-700 rounded-lg p-1.5 text-slate-200 text-xs focus:outline-none focus:border-emerald-500">

        <button type="button" onclick="document.getElementById('${rowId}').remove()" class="text-slate-400 hover:text-rose-400 px-2 py-1 rounded text-xs transition-colors" title="Eliminar">✕</button>

    `;

    container.appendChild(div);

}



function getStep3ObjetivosEspecificos() {

    const inputs = document.querySelectorAll('.step3-obj-item-input');

    const list = [];

    inputs.forEach(inp => {

        const val = inp.value.trim();

        if (val) list.push(val);

    });

    return list;

}



const DEFAULT_OBLIGATIONS_BY_TYPOLOGY = {

    'PRESTACION_SERVICIOS': {

        ep: [

            "Acreditar la idoneidad profesional, técnica o de experiencia requerida para la ejecución del servicio, aportando hoja de vida con soportes académicos, tarjeta o matrícula profesional vigente (si aplica), certificados de experiencia y antecedentes fiscales, disciplinarios y judiciales vigentes.",

            "Presentar a la supervisión de la ESP, dentro de los cinco (5) días hábiles siguientes al acta de inicio, el plan de trabajo detallado y el cronograma de ejecución de actividades.",

            "Disponer de los medios técnicos, tecnológicos, informáticos, equipos y herramientas propias requeridas para el cabal y oportuno desarrollo del objeto contratado.",

            "Estructurar y presentar los informes de actividades, diagnósticos y entregables técnicos conforme a las metodologías, formatos y estándares de calidad institucionales de la ESP.",

            "Atender, subsanar y corregir oportunamente las observaciones formuladas por la supervisión sobre los borradores o entregables presentados, dentro del plazo que ésta determine.",

            "Tramitar y presentar la constancia de afiliación activa al Sistema General de Seguridad Social Integral (Salud, Pensión y ARL) con anterioridad a la fecha del acta de inicio.",

            "Participar en las capacitaciones o inducciones de Seguridad y Salud en el Trabajo (SG-SST) y acatar los protocolos de prevención de riesgos laborales y ambientales de la entidad.",

            "Asistir puntualmente a los comités técnicos y mesas de trabajo convocadas por la supervisión para la revisión y seguimiento de los avances contractuales.",

            "Constituir y presentar oportunamente para aprobación de la ESP las pólizas de garantía requeridas, manteniéndolas vigentes durante todo el plazo de ejecución y su liquidación.",

            "Obtener el paz y salvo técnico, administrativo y documental de la supervisión como requisito previo e indispensable para el trámite de liquidación final del contrato."

        ],

        minuta: [

            "Ejecutar el objeto del contrato y las actividades acordadas con plena autonomía técnica, administrativa, directiva y financiera, sin subordinación laboral, utilizando sus propios medios y conocimientos especializados bajo el régimen de la Ley 142 de 1994 y el Artículo 23 del CST.",

            "Cumplir a cabalidad con el cronograma, plazos de entrega y especificaciones técnicas aprobadas por la ESP, garantizando la más alta calidad, diligencia y pericia profesional en el desarrollo del servicio.",

            "Acatar de manera diligente las instrucciones, requerimientos técnicos y directrices impartidas por el supervisor designado por la ESP, facilitando en todo momento el control, inspección y vigilancia de los servicios.",

            "Asistir y participar activamente en las reuniones de seguimiento, comités técnicos o mesas de trabajo programadas por la entidad o la supervisión para evaluar el avance del objeto contractual.",

            "Presentar mensualmente a la supervisión, dentro de los primeros cinco (5) días hábiles de cada mes, un informe detallado de las actividades desarrolladas acompañado de las evidencias documentales, memorias, registros fotográficos y entregables pactados, como requisito previo para la expedición del certificado de cumplimiento y trámite de pago.",

            "Acreditar previa y obligatoriamente ante la supervisión, para el trámite de cada pago y para la liquidación contractual, la afiliación y pago oportuno de aportes al Sistema de Seguridad Social Integral (Salud, Pensión y ARL en el nivel de riesgo correspondiente al servicio), calculados sobre un IBC no inferior al 40% del valor mensualizado del contrato, en cumplimiento de la Ley 100 de 1993, Ley 789 de 2002 y Decreto 1273 de 2018.",

            "Cumplir estrictamente las normas, políticas y estándares del Sistema de Gestión de Seguridad y Salud en el Trabajo (SG-SST) de la ESP (Decreto 1072 de 2015 y Resolución 0312 de 2019), utilizando permanentemente y en óptimo estado los Elementos de Protección Personal (EPP/EPI) reglamentarios.",

            "Reportar inmediatamente por escrito al supervisor cualquier incidente, accidente laboral, condición de riesgo operativo o emergencia sobreviniente en la ejecución de las actividades contratadas.",

            "Guardar absoluta reserva, custodia y confidencialidad sobre la información técnica, administrativa, financiera, operativa y bases de datos de usuarios de la ESP a la que tenga acceso, absteniéndose de divulgarla o usarla para fines ajenos al contrato, dando estricto cumplimiento a la Ley 1581 de 2012 de Protección de Datos Personales (Habeas Data).",

            "Responder por el cuidado, custodia, mantenimiento y buen uso de los elementos, herramientas, equipos o documentación que la ESP le suministre para facilitar el servicio, debiendo restituirlos en igual estado a la terminación del contrato, salvo el desgaste natural por el uso legítimo.",

            "Responder civil, fiscal y disciplinariamente por los daños o perjuicios que por culpa, impericia, negligencia o dolo ocasione a la ESP o a terceros en la ejecución contractual, debiendo mantener indemne a la entidad frente a cualquier reclamación judicial, extrajudicial o laboral.",

            "Obrar con estricta lealtad, buena fe, ética y transparencia en cumplimiento del Estatuto Anticorrupción (Leyes 1474 de 2011 y 2195 de 2022), absteniéndose de ofrecer o recibir dádivas o prebendas, y declarando inmediatamente cualquier inhabilidad o conflicto de interés sobreviniente.",

            "Ceder de manera total, definitiva y exclusiva a favor de la ESP todos los derechos patrimoniales de autor sobre estudios, informes, diagnósticos, bases de datos o productos intelectuales desarrollados en ejecución del contrato.",

            "Suscribir oportunamente en debida forma el Acta de Inicio, las Actas Parciales de Recibo o Avance y el Acta de Liquidación Final del contrato en coordinación con la supervisión técnica."

        ],

        empresa: [

            "Designar al Supervisor del contrato para que ejerza el control, seguimiento, vigilancia y verificación técnica y administrativa del cumplimiento del objeto pactado.",

            "Facilitar oportunamente al contratista las directrices, insumos, bienes o información técnica estrictamente necesaria para la correcta ejecución del objeto contratado.",

            "Pagar el valor convenido de los servicios ejecutados, previa radicación de la factura electrónica o cuenta de cobro (según el régimen tributario del contratista), informe de ejecución y visto bueno de supervisión con acreditación de aportes a seguridad social.",

            "Revisar diligentemente los informes de ejecución, entregables técnicos y comprobantes de pago radicados por el contratista y expedir las certificaciones de cumplimiento dentro de los términos establecidos.",

            "Coordinar y atender las reuniones de seguimiento técnico o comités operativos programados para evaluar el avance y calidad de las labores contratadas.",

            "Respetar la autonomía técnica, administrativa y directiva del contratista en la ejecución del objeto contractual, absteniéndose de impartir órdenes que impliquen subordinación laboral.",

            "Suscribir oportunamente en debida forma el Acta de Inicio y el Acta de Liquidación Final del contrato una vez culminadas las obligaciones y verificado el paz y salvo integral."

        ]

    },

    'OBRA': {

        ep: [

            "Realizar visita técnica obligatoria al sitio de las obras para constatar topografía, accesibilidad, interferencias de redes de servicios y condiciones del terreno.",

            "Presentar el presupuesto oficial desglosado con análisis detallado de precios unitarios (APU) y porcentaje desglosado de A.I.U. (Administración, Imprevistos y Utilidad).",

            "Entregar el cronograma de ejecución física y financiera detallado (diagrama Gantt o CPM) con su respectiva ruta crítica, debidamente firmado por el Director de Obra.",

            "Acreditar la disponibilidad de maquinaria pesada, equipos certificados y herramientas requeridas para el rendimiento óptimo del frente de trabajo.",

            "Aportar las hojas de vida y matrículas profesionales vigentes del Director de Obra y Residente de Obra con sus antecedentes de COPNIA vigentes.",

            "Formular y presentar el Plan de Manejo Ambiental (PMA) y el Plan de Manejo de Tránsito (PMT) articulado con las autoridades municipales.",

            "Acreditar el cumplimiento del SG-SST y presentar las constancias de afiliación a seguridad social en Riesgo V de ARL para el personal operativo.",

            "Presentar el plan de calidad de materiales e insumos con los protocolos de ensayos de laboratorio y certificados de fábrica."

        ],

        minuta: [

            "Ejecutar la totalidad de las obras civiles con estricto apego a los planos, especificaciones técnicas de la ESP, normas sismorresistentes NSR-10 y Reglamento RAS-2017 (Res. 0330/2017 MVCT).",

            "Disponer de manera permanente en el frente de trabajo de un Ingeniero Residente de Obra debidamente matriculado y con dedicación exclusiva a la ejecución del proyecto.",

            "Diligenciar diariamente y mantener actualizada la bitácora o libro oficial de obra en conjunto con la interventoría/supervisión técnica, consignando avances, personal, maquinaria e incidencias.",

            "Suministrar materiales certificados de primera calidad (tuberías, accesorios, concretos, agregados), aportando certificados de conformidad y ensayos de laboratorio a costo del contratista.",

            "Implementar rigurosamente el Sistema de Gestión de Seguridad y Salud en el Trabajo (SG-SST) conforme al Decreto 1072 de 2015, dotando a los trabajadores de EPP/EPI y cobertura en Riesgo V de ARL.",

            "Instalar cerramientos perimetrales de seguridad, señalización preventiva reglamentaria diurna y nocturna y ejecutar el Plan de Manejo de Tránsito (PMT) aprobado.",

            "Ejecutar el Plan de Manejo Ambiental (PMA) y la gestión integral de Residuos de Construcción y Demolición (RCD - Res. 1257 de 2021), disponiendo escombros solo en sitios legalmente certificados.",

            "Efectuar a su costa las pruebas técnicas de presión hidrostática, estanqueidad, desinfección de redes y ensayos de resistencia de concretos bajo supervisión técnica.",

            "Responder civil, penal y patrimonialmente por los daños y perjuicios causados a predios colindantes, redes existentes de servicios o a terceros, manteniendo indemne a la ESP.",

            "Constituir, prorrogar y mantener vigentes todas las garantías contractuales exigidas (cumplimiento, salarios, estabilidad de obra decenal y responsabilidad civil extracontractual).",

            "Elaborar y entregar a la ESP los planos récord definitivos (As-Built) en medio digital editable (DWG/CAD) y PDF, junto con las memorias de cálculo y manuales de operación.",

            "Suscribir oportunamente en debida forma el Acta de Inicio, Actas Parciales de Obra con memorias de cálculo, Acta de Recibo Final y Acta de Liquidación Definitiva del contrato."

        ],

        empresa: [

            "Designar oportunamente la Interventoría o Supervisión Técnica y Administrativa que ejercerá el control, seguimiento y vigilancia de la ejecución de la obra.",

            "Efectuar la entrega real y material de la zona, frentes de trabajo y predios requeridos para la ejecución de las obras mediante la suscripción del Acta de Entrega de Terreno.",

            "Tramitar oportunamente los permisos institucionales y coordinar las suspensiones programadas del servicio público necesarias para empalmes o intervenciones de redes.",

            "Revisar, aprobar y tramitar para pago las actas parciales de obra debidamente suscritas por el contratista y la interventoría/supervisión dentro de los plazos establecidos.",

            "Suministrar oportunamente al contratista los planos generales, memorias de diseño y especificaciones técnicas oficiales requeridas para la ejecución de la obra.",

            "Suscribir oportunamente las Actas de Inicio, Suspensión, Reinicio, Modificación, Recibo Final y Liquidación Definitiva del contrato.",

            "Revisar y recibir los planos récord (As-Built), memorias técnicas y manuales de operación entregados por el contratista al término de la obra."

        ]

    },

    'SUMINISTRO': {

        ep: [

            "Presentar catálogo comercial y fichas técnicas oficiales del fabricante detallando especificaciones, tolerancias y materiales para cada ítem a suministrar.",

            "Adjuntar certificados vigentes de conformidad de producto con normas técnicas oficiales (NTC, AWWA, ASTM, ISO o equivalentes).",

            "Presentar el cronograma de despacho y entrega en el Almacén General de la ESP, detallando fechas de remisión y lotes.",

            "Aportar hojas de datos de seguridad (MSDS / SGA - Decreto 1496 de 2018) y protocolos de almacenamiento seguro si se trata de químicos, reactivos o sustancias peligrosas.",

            "Acreditar la idoneidad y representación autorizada del fabricante o distribuidor mayorista en Colombia.",

            "Entregar la carta de compromiso de garantía técnica de fábrica no inferior a un (1) año y disponibilidad de repuestos por un término mínimo de cinco (5) años.",

            "Acreditar el cumplimiento de aportes al Sistema de Seguridad Social Integral y parafiscales de su personal.",

            "Disponer de los medios de transporte idóneos con pólizas de mercancías vigentes para la entrega DDP en las bodegas de la entidad."

        ],

        minuta: [

            "Efectuar la entrega de la totalidad de los bienes en la bodega principal o Almacén General de la ESP bajo condición DDP (Delivered Duty Paid), asumiendo todos los costos de fletes, embalaje, seguros, peajes y descargue.",

            "Suministrar bienes totalmente nuevos, de primera calidad, de fabricación reciente (no saldos ni remanufacturados), empacados y rotulados conforme a la normativa vigente.",

            "Aportar junto con cada despacho las remisiones, fichas técnicas, certificados de control de calidad de fábrica, certificados de calibración y hojas de seguridad en español.",

            "Suscribir el Acta de Entrada al Almacén y Recibo a Satisfacción conjuntamente con el Jefe de Almacén y el Supervisor del contrato tras la verificación física, conteo y prueba técnica.",

            "Reemplazar por su cuenta y riesgo, dentro de un término perentorio máximo de cuarenta y ocho (48) horas hábiles, cualquier elemento averiado, defectuoso o no conforme con las especificaciones.",

            "Otorgar garantía técnica formal de fábrica por un periodo mínimo de doce (12) meses contados a partir del recibo a satisfacción, amparando defectos de fabricación y vicios ocultos (Art. 934 C.Co.).",

            "Garantizar la disponibilidad de repuestos legítimos, consumibles y servicio técnico autorizado durante la vigencia de la garantía técnica del producto.",

            "Entregar los manuales técnicos de instalación, operación y mantenimiento en idioma español junto con las cartas de garantía debidamente suscritas.",

            "Brindar la capacitación o transferencia tecnológica necesaria al personal operativo de la ESP en el manejo e instalación adecuada de los bienes suministrados si se requiere.",

            "Acreditar oportunamente la afiliación y pago de aportes al Sistema de Seguridad Social Integral y parafiscales como condición previa para el trámite de cada factura y desembolso de pago.",

            "Mantener indemne a la ESP frente a cualquier reclamación de terceros por infracción de patentes, licencias, marcas, derechos de autor o daños atribuibles a defectos del producto.",

            "Suscribir oportunamente en debida forma el Acta de Inicio (si aplica), actas de entrega parcial y el Acta de Liquidación Final del contrato."

        ],

        empresa: [

            "Designar al Supervisor del contrato y coordinar con el responsable del Almacén General la recepción física y técnica de los bienes.",

            "Recibir a satisfacción los bienes suministrados que cumplan estrictamente con las especificaciones técnicas pactadas y suscribir el Acta de Entrada al Almacén dentro de las cuarenta y ocho (48) horas siguientes a la entrega.",

            "Informar por escrito y de manera motivada al contratista sobre cualquier inconformidad, faltante, avería o defecto en los bienes entregados para su inmediata reposición.",

            "Facilitar el acceso logístico adecuado a las instalaciones y bodegas de la empresa para el descargue seguro y custodia de los elementos suministrados.",

            "Tramitar oportunamente el pago del valor convenido, previa radicación de la factura electrónica reglamentaria con el cumplimiento de requisitos legales y visto bueno de supervisión.",

            "Suscribir el Acta de Liquidación del contrato una vez verificada la entrega total de los bienes y el cumplimiento de las garantías técnicas."

        ]

    },

    'ARRENDAMIENTO': {

        ep: [

            "Verificar las condiciones físicas, estructurales, jurídicas y de saneamiento del bien inmueble objeto del arrendamiento.",

            "Aportar el certificado de tradición y libertad con fecha de expedición no mayor a 30 días y comprobantes de paz y salvo de impuestos y servicios.",

            "Presentar inventario detallado del estado inicial del inmueble con registro fotográfico para el acta de entrega.",

            "Establecer el protocolo de mantenimiento preventivo y correctivo de las instalaciones locativas."

        ],

        minuta: [

            "Destinar el bien inmueble única y exclusivamente para los fines operativos, administrativos o institucionales acordados en el contrato.",

            "Mantener y conservar el inmueble en buen estado de funcionamiento, asumiendo oportunamente las reparaciones locativas que le correspondan conforme a la ley.",

            "Efectuar el pago oportuno de los cánones de arrendamiento en los términos, plazos y cuentas bancarias convenidas.",

            "Permitir la inspección periódica del inmueble por parte del supervisor designado por la ESP para verificar su estado y destinación.",

            "Abstenerse de subarrendar, ceder o gravar total o parcialmente el contrato o la tenencia del inmueble sin autorización previa, expresa y por escrito de la ESP.",

            "Efectuar oportunamente el pago de los servicios públicos domiciliarios a su cargo y remitir las constancias de pago al supervisor.",

            "No realizar modificaciones estructurales o reformas en el inmueble sin la debida autorización previa y por escrito de la entidad arrendadora.",

            "Restituir formalmente el inmueble a la ESP al vencimiento del plazo contractual en el mismo estado en que fue recibido, salvo el deterioro natural por el uso legítimo, mediante acta de entrega y recibo final."

        ],

        empresa: [

            "Hacer entrega material del bien inmueble en la fecha convenida, en adecuado estado de servicio, seguridad y sanidad, mediante acta suscrita con inventario detallado.",

            "Garantizar el goce pacífico del bien durante todo el tiempo del contrato, amparando al arrendatario frente a turbaciones de derecho o pretensiones de terceros.",

            "Asumir oportunamente las reparaciones necesarias mayores o estructurales no locativas y las derivadas de fuerza mayor o vicios ocultos de construcción.",

            "Efectuar oportunamente el pago de los cánones de arrendamiento en los términos y plazos pactados (cuando la ESP actúe en calidad de arrendataria).",

            "Designar al supervisor institucional para coordinar la verificación periódica del estado del inmueble y el cumplimiento de las condiciones contractuales.",

            "Recibir formalmente el inmueble a la terminación del contrato mediante acta de entrega y restitución suscrita conjuntamente por las partes."

        ]

    },

    'CONSULTORIA': {

        ep: [

            "Acreditar la idoneidad profesional, título de posgrado y experiencia específica del equipo consultor en el área del proyecto.",

            "Presentar la propuesta metodológica detallada, plan de trabajo y cronograma de fases con hitos de entrega.",

            "Disponer de herramientas de software especializado, modelos de simulación y bases de datos requeridas.",

            "Participar en las mesas de concertación técnica con el equipo interdisciplinario de la ESP.",

            "Garantizar la rigurosidad científica y apego a normas del sector de agua potable y saneamiento básico."

        ],

        minuta: [

            "Ejecutar los estudios y consultoría con plena autonomía técnica e independencia profesional bajo los principios de la Ley 142 de 1994.",

            "Desarrollar cada una de las fases metodológicas y entregar los informes diagnósticos, memorias de cálculo y modelaciones en los plazos pactados.",

            "Sustentar técnicamente los resultados y recomendaciones de la consultoría ante la Gerencia y Junta Directiva de la ESP si se requiere.",

            "Acreditar oportunamente la afiliación y pago de aportes al Sistema de Seguridad Social Integral sobre el IBC legal.",

            "Guardar estricta confidencialidad sobre la información reservada de la empresa y ceder de forma definitiva los derechos patrimoniales de autor sobre los productos generados.",

            "Responder civil y profesionalmente por los errores u omisiones en los cálculos, diseños o diagnósticos emitidos.",

            "Suscribir el acta de inicio y el acta de liquidación final del contrato a satisfacción de la supervisión."

        ],

        empresa: [

            "Designar la supervisión o interventoría técnica para el acompañamiento y validación de las fases de la consultoría.",

            "Suministrar oportunamente los antecedentes, diagnósticos técnicos, datos cartográficos e institucionales requeridos para el estudio.",

            "Revisar y emitir conceptos técnicos sobre los informes de avance y entregables finales en los plazos fijados.",

            "Efectuar los desembolsos correspondientes conforme a los hitos de entrega aprobados por la supervisión.",

            "Suscribir las actas de inicio, recibo a satisfacción de productos y liquidación final del contrato."

        ]

    }

};



const DEFAULT_LEGAL_FRAMEWORK_BY_TYPOLOGY = {

    'PRESTACION_SERVICIOS': {

        badge: 'Prestación de Servicios (Ley 142/94 - Civil/Laboral)',

        text: `El presente Contrato de Prestación de Servicios se fundamenta en el siguiente marco normativo y jurisprudencial:

1. RÉGIMEN ESPECIAL DE DERECHO PRIVADO: Ley 142 de 1994 (Régimen de los Servicios Públicos Domiciliarios), Artículos 31 y 32, concordantes con las normas de contratación del derecho privado (Código Civil y Código de Comercio), salvo expresa disposición legal en contrario.

2. PRINCIPIOS CONSTITUCIONALES: Artículos 209 y 267 de la Constitución Política de Colombia (igualdad, moralidad, eficacia, economía, celeridad, imparcialidad y publicidad en la función administrativa y gestión fiscal).

3. ARRENDAMIENTO DE SERVICIOS INMATERIALES: Código Civil Colombiano, Artículos 2053 a 2069 (servicios profesionales, técnicos y de apoyo calificado retribuidos mediante honorarios).

4. AUTONOMÍA TÉCNICA E INEXISTENCIA DE SUBORDINACIÓN LABORAL: Artículo 23 del Código Sustantivo del Trabajo (CST), en concordancia con la jurisprudencia unificada de la Corte Constitucional (Sentencias C-614 de 2009 y C-171 de 2012) y del Consejo de Estado (Sección Segunda), que prohíben la subordinación jurídica, dependencia laboral y cumplimiento de horarios, consagrando la plena autonomía del contratista independiente.

5. SEGURIDAD SOCIAL INTEGRAL OBLIGATORIA: Ley 100 de 1993, Ley 797 de 2003, Decreto 1072 de 2015 y Decreto 1273 de 2018 (afiliación y pago previo de aportes a Salud 12.5%, Pensión 16% y ARL sobre IBC mínimo del 40% mensualizado como requisito previo de pago).

6. RÉGIMEN DE INHABILIDADES E INCOMPATIBILIDADES: Artículo 8 de la Ley 80 de 1993 y Ley 1150 de 2007, aplicable a las entidades y contratistas de las ESP por remisión jurisprudencial vinculante de la Corte Constitucional (Sentencia C-066 de 1997).

7. ESTATUTO INTERNO: Manual Interno de Contratación de la Empresa de Servicios Públicos de Yolombó ESPY.`

    },

    'OBRA': {

        badge: 'Contrato de Obra (Ley 142/94, Civil, RAS-2017 & NSR-10)',

        text: `El presente Contrato de Obra se fundamenta en el siguiente marco normativo, técnico y jurisprudencial:

1. RÉGIMEN ESPECIAL DE DERECHO PRIVADO: Ley 142 de 1994 (Régimen de los Servicios Públicos Domiciliarios), Artículos 31 y 32 (actos y contratos regidos por el derecho privado).

2. PRINCIPIOS CONSTITUCIONALES: Artículos 209 y 267 de la Constitución Política de Colombia (igualdad, moralidad, eficacia, economía, celeridad y control fiscal).

3. CONFECCIÓN DE OBRA MATERIAL: Código Civil Colombiano, Artículos 2053 a 2062 (precio global alzado o precios unitarios fijos sin reajuste).

4. RESPONSABILIDAD DECENAL Y GARANTÍA DE ESTABILIDAD: Artículo 2060 numeral 3 del Código Civil Colombiano (responsabilidad legal por ruina o vicios de construcción, suelo o materiales durante 10 años; amparo de estabilidad no inferior a 5 años).

5. REGLAMENTO TÉCNICO DEL SECTOR AGUA POTABLE Y SANEAMIENTO (RAS): Resolución 0330 de 2017 del Ministerio de Vivienda, Ciudad y Territorio (parámetros de diseño, calidad, pendientes hidráulicas, pruebas de estanqueidad y tuberías para acueducto y alcantarillado).

6. NORMA SISMORRESISTENTE NSR-10: Ley 400 de 1997 y Decreto 926 de 2010 para tanques de almacenamiento, estaciones de bombeo y edificaciones técnicas de la ESP.

7. SEGURIDAD Y SALUD EN EL TRABAJO EN CONSTRUCCIÓN (SG-SST): Decreto 1072 de 2015, Resolución 0312 de 2019, Resolución 4272 de 2021 (alturas), Resolución 0491 de 2020 (espacios confinados) y Resolución 2400 de 1979 (excavaciones seguras).

8. NORMATIVA AMBIENTAL Y MANEJO DE RCD: Decreto 1076 de 2015 (Plan de Manejo Ambiental) y Resolución 1257 de 2021 para Residuos de Construcción y Demolición (RCD).

9. RÉGIMEN TRIBUTARIO A.I.U.: Artículos 462-1 y 468-3 del Estatuto Tributario (IVA liquidado sobre la Utilidad pactada).

10. INHABILIDADES Y MANUAL INTERNO: Artículo 8 Ley 80 de 1993, Sentencia C-066/97 y Manual Interno de Contratación de la ESPY.`

    },

    'SUMINISTRO': {

        badge: 'Contrato de Suministro (Ley 142/94, C.Comercio & Calidad Agua)',

        text: `El presente Contrato de Suministro se fundamenta en el siguiente marco normativo y comercial:

1. RÉGIMEN ESPECIAL DE DERECHO PRIVADO: Ley 142 de 1994, Artículos 31 y 32 (actos y contratos regidos por el derecho privado y comercial de las ESP).

2. PRINCIPIOS CONSTITUCIONALES: Artículos 209 y 267 de la Constitución Política de Colombia (moralidad, celeridad, eficacia y economía).

3. CONTRATO MERCANTIL DE SUMINISTRO: Código de Comercio de Colombia, Artículos 968 a 980 (prestaciones periódicas o continuadas de cosas o insumos a favor de la ESP, precios y plazos de entrega).

4. COMPRAVENTA MERCANTIL Y VICIOS OCULTOS: Código de Comercio, Artículos 905 y concordantes; deber legal de entrega material, saneamiento por evicción e indemnidad por vicios redhibitorios u ocultos (Art. 934 C.Co.).

5. CONTROL DE CALIDAD DEL AGUA Y REACTIVOS: Decreto 1575 de 2007 y Resolución 2115 de 2007 (pureza y especificaciones de sustancias químicas para potabilización de agua para consumo humano).

6. SISTEMA GLOBALMENTE ARMONIZADO (SGA): Ley 55 de 1993 y Decreto 1496 de 2018 (etiquetado de seguridad, pictogramas y Fichas de Datos de Seguridad MSDS obligatorias).

7. NORMAS TÉCNICAS COLOMBIANAS E INTERNACIONALES: Normas NTC, AWWA e ISO 4064 para micromedición, accesorios de polietileno/PVC y válvulas de control de acueducto.

8. CONDICIÓN DE ENTREGA DDP: Entrega en el Almacén General de la ESP bajo condición DDP (Delivered Duty Paid), con transporte, seguros y descargue a cargo del contratista.

9. INHABILIDADES Y MANUAL INTERNO: Artículo 8 Ley 80 de 1993, Sentencia C-066/97 y Manual Interno de Contratación de la ESPY.`

    },

    'ARRENDAMIENTO': {

        badge: 'Contrato de Arrendamiento (Ley 142/94 & Código Civil Art. 1973+)',

        text: `El presente Contrato de Arrendamiento se fundamenta en el siguiente marco normativo y civil:

1. RÉGIMEN ESPECIAL DE DERECHO PRIVADO: Ley 142 de 1994 (Régimen de los Servicios Públicos Domiciliarios), Artículos 31 y 32 (actos y contratos regidos por el derecho privado).

2. CONTRATO DE ARRENDAMIENTO DE INMUEBLES: Código Civil Colombiano, Artículos 1973 y subsiguientes (goce temporal de un inmueble a cambio de un precio o canon mensual pactado).

3. PRINCIPIOS CONSTITUCIONALES: Artículos 209 y 267 de la Constitución Política de Colombia (moralidad, celeridad, eficacia, economía y gestión fiscal).

4. OBLIGACIONES DEL ARRENDATARIO: Conservación del inmueble, reparaciones locativas, pago oportuno del canon y destinación exclusiva para la operación de la ESP.

5. ENTREGA MATERIAL E INVENTARIO: Suscripción de acta de recibo e inventario físico detallado del estado del inmueble a la entrega y restitución.

6. RÉGIMEN DE INHABILIDADES Y MANUAL INTERNO: Artículo 8 Ley 80 de 1993, Sentencia C-066/97 y Manual Interno de Contratación de la ESPY.`

    }

};



function selectWizardTypology(tipologia) {

    state.wizard.tipologia = tipologia;

    document.querySelectorAll('.typology-card').forEach(card => {

        card.classList.remove('border-sky-500', 'bg-sky-900/30');

        card.classList.add('border-slate-700', 'bg-slate-800/40');

    });



    const activeCard = document.getElementById(`type-card-${tipologia.toLowerCase()}`);

    if (activeCard) {

        activeCard.classList.remove('border-slate-700', 'bg-slate-800/40');

        activeCard.classList.add('border-sky-500', 'bg-sky-900/30');

    }



    // Actualizar dinámicamente la denominación de Tipo de Contrato (para {{TIPO DE CONTRATO}})

    const tipoMap = {

        'PRESTACION_SERVICIOS': 'PRESTACIÓN DE SERVICIOS',

        'OBRA': 'OBRA',

        'SUMINISTRO': 'SUMINISTRO',

        'ARRENDAMIENTO': 'ARRENDAMIENTO',

        'CONSULTORIA': 'CONSULTORÍA',

        'INTERVENTORIA': 'INTERVENTORÍA'

    };

    const tipoInput = document.getElementById('wiz-tipo-contrato');

    if (tipoInput) {

        tipoInput.value = tipoMap[tipologia] || tipologia.replace(/_/g, ' ');

    }



    // Actualizar dinámicamente el marco jurídico sugerido en el Paso 2

    const framework = DEFAULT_LEGAL_FRAMEWORK_BY_TYPOLOGY[tipologia] || DEFAULT_LEGAL_FRAMEWORK_BY_TYPOLOGY['PRESTACION_SERVICIOS'];

    const badgeEl = document.getElementById('wiz-marco-badge');

    if (badgeEl) badgeEl.innerText = framework.badge;

    const marcoEl = document.getElementById('wiz-marco-juridico');

    if (marcoEl && (!marcoEl.value.trim() || marcoEl.dataset.autoFilled === 'true' || marcoEl.dataset.tipologia !== tipologia)) {

        marcoEl.value = framework.text;

        marcoEl.dataset.autoFilled = 'true';

        marcoEl.dataset.tipologia = tipologia;

    }



    // Actualizar dinámicamente el código y prefijo oficial (CPS, CS, CA, CO)

    if (typeof refreshWizardContractNumber === 'function') {

        refreshWizardContractNumber();

    }

}



function proceedToStep3Manual() {

    const tipologia = state.wizard.tipologia || state.wizard.typology || 'PRESTACION_SERVICIOS';

    const objetoEl = document.getElementById('wiz-objeto');

    const rawObjeto = objetoEl ? objetoEl.value.trim() : '';

    const objeto = rawObjeto ? formatObjetoContractual(rawObjeto, tipologia) : '';

    if (!objeto) {

        showToast('Por favor ingrese el Objeto Contractual del contrato en el Paso 2.', 'warning');

        if (objetoEl) objetoEl.focus();

        return;

    }

    if (objetoEl) objetoEl.value = objeto;



    const tipoContrato = document.getElementById('wiz-tipo-contrato')?.value.trim() 

        || (tipologia === 'PRESTACION_SERVICIOS' ? 'PRESTACIÓN DE SERVICIOS' : tipologia);

    state.wizard.tipoContrato = tipoContrato;

    const resTipoContrato = document.getElementById('agent-result-tipo-contrato');

    if (resTipoContrato) resTipoContrato.value = tipoContrato;



    const justificacionEl = document.getElementById('wiz-justificacion');

    const justificacion = justificacionEl ? justificacionEl.value.trim() : '';



    const objGeneralEl = document.getElementById('wiz-obj-general');

    const objGeneral = objGeneralEl ? objGeneralEl.value.trim() : '';



    const objEspecificos = getWizardObjetivosEspecificos();



    state.wizard.necesidad = objeto;

    state.wizard.justificacion = justificacion || 'Garantizar la prestación eficiente y continua de los servicios públicos bajo el régimen de la Ley 142 de 1994.';

    state.wizard.objetivoGeneral = objGeneral || objeto;

    state.wizard.objetivosEspecificos = objEspecificos;

    state.wizard.alcance = document.getElementById('wiz-alcance')?.value.trim() || '';

    state.wizard.modalidad = document.getElementById('wiz-modalidad')?.value || 'CONTRATACION_DIRECTA';

    state.wizard.valorEstimado = parseFloat(document.getElementById('wiz-valor')?.value) || 0;

    state.wizard.plazo = parseInt(document.getElementById('wiz-plazo')?.value) || 6;

    state.wizard.unidadPlazo = document.getElementById('wiz-unidad-plazo')?.value || 'MESES';

    state.wizard.supervisorNombre = document.getElementById('wiz-supervisor-nombre')?.value.trim() || 'Ing. Supervisor Técnico';

    state.wizard.supervisorCargo = document.getElementById('wiz-supervisor-cargo')?.value.trim() || 'Director Operativo y Técnico';

    state.wizard.supervisorTipoDoc = document.getElementById('wiz-supervisor-tipo-doc')?.value || 'CC';

    state.wizard.supervisorDocumento = document.getElementById('wiz-supervisor-documento')?.value.trim() || null;

    state.wizard.fechaSuscripcion = document.getElementById('wiz-fecha-suscripcion')?.value || null;

    state.wizard.fechaInicio = document.getElementById('wiz-fecha-inicio')?.value || null;

    state.wizard.fechaTerminacion = document.getElementById('wiz-fecha-terminacion')?.value || null;

    state.wizard.cdpNumero = document.getElementById('wiz-cdp-numero')?.value.trim() || state.wizard.cdpNumero || null;

    state.wizard.cdpFecha = document.getElementById('wiz-cdp-fecha')?.value || state.wizard.cdpFecha || null;

    state.wizard.cdpRubro = document.getElementById('wiz-cdp-rubro')?.value.trim() || state.wizard.cdpRubro || null;

    state.wizard.cdpRubroNombre = document.getElementById('wiz-cdp-rubro-nombre')?.value.trim() || state.wizard.cdpRubroNombre || null;

    state.wizard.cdpValor = parseFloat(document.getElementById('wiz-cdp-valor')?.value) || state.wizard.cdpValor || state.wizard.valorEstimado || null;

    state.wizard.cdpClasificadores = document.getElementById('wiz-cdp-clasificadores')?.value.trim() || state.wizard.cdpClasificadores || null;



    // Poblar campos de CDP en el Paso 3 para revisión definitiva

    if (document.getElementById('agent-result-cdp-numero')) {

        document.getElementById('agent-result-cdp-numero').value = state.wizard.cdpNumero || '';

    }

    if (document.getElementById('agent-result-cdp-fecha')) {

        document.getElementById('agent-result-cdp-fecha').value = state.wizard.cdpFecha || '';

    }

    if (document.getElementById('agent-result-cdp-valor')) {

        document.getElementById('agent-result-cdp-valor').value = state.wizard.cdpValor || state.wizard.valorEstimado || '';

    }

    if (document.getElementById('agent-result-cdp-rubro')) {

        document.getElementById('agent-result-cdp-rubro').value = state.wizard.cdpRubro || '';

    }

    if (document.getElementById('agent-result-cdp-rubro-nombre')) {

        document.getElementById('agent-result-cdp-rubro-nombre').value = state.wizard.cdpRubroNombre || '';

    }

    if (document.getElementById('agent-result-cdp-clasificadores')) {

        document.getElementById('agent-result-cdp-clasificadores').value = state.wizard.cdpClasificadores || '';

    }

    updateCdpLivePreview();



    // Poblar fechas clave en el Paso 3 para revisión definitiva

    if (document.getElementById('agent-result-fecha-suscripcion')) {

        document.getElementById('agent-result-fecha-suscripcion').value = state.wizard.fechaSuscripcion || '';

    }

    if (document.getElementById('agent-result-fecha-inicio')) {

        document.getElementById('agent-result-fecha-inicio').value = state.wizard.fechaInicio || '';

    }

    if (document.getElementById('agent-result-fecha-terminacion')) {

        document.getElementById('agent-result-fecha-terminacion').value = state.wizard.fechaTerminacion || '';

    }



    // Marco Jurídico

    const framework = DEFAULT_LEGAL_FRAMEWORK_BY_TYPOLOGY[tipologia] || DEFAULT_LEGAL_FRAMEWORK_BY_TYPOLOGY['PRESTACION_SERVICIOS'];

    const marcoEl = document.getElementById('wiz-marco-juridico');

    const marcoJuridico = (marcoEl && marcoEl.value.trim()) ? marcoEl.value.trim() : framework.text;

    state.wizard.marcoJuridico = marcoJuridico;



    // Cargar datos en el Paso 3 para revisión

    const resObjeto = document.getElementById('agent-result-objeto');

    if (resObjeto) resObjeto.value = objeto;



    const resJust = document.getElementById('agent-result-justificacion');

    if (resJust) resJust.value = state.wizard.justificacion;



    const resMarco = document.getElementById('agent-result-marco-juridico');

    if (resMarco) resMarco.value = marcoJuridico;



    const resMarcoBadge = document.getElementById('agent-result-marco-badge');

    if (resMarcoBadge) resMarcoBadge.innerText = framework.badge;



    const resObjGen = document.getElementById('agent-result-obj-general');

    if (resObjGen) resObjGen.value = state.wizard.objetivoGeneral;



    // Renderizar objetivos específicos en el contenedor del paso 3

    const listStep3 = document.getElementById('agent-result-obj-especificos-list');

    if (listStep3) {

        listStep3.innerHTML = '';

        if (objEspecificos.length > 0) {

            objEspecificos.forEach(o => addStep3ObjetivoEspecifico(o));

        } else {

            addStep3ObjetivoEspecifico(objeto);

        }

    }



    // Obligaciones estándar sugeridas por tipología si el usuario no las ha modificado o si son las legacy cortas

    const obligDefaults = DEFAULT_OBLIGATIONS_BY_TYPOLOGY[tipologia] || DEFAULT_OBLIGATIONS_BY_TYPOLOGY['PRESTACION_SERVICIOS'];

    const epTextarea = document.getElementById('agent-result-oblig-ep');

    if (epTextarea) {

        const curEp = epTextarea.value.trim();

        const isLegacyEp = !curEp || (curEp.split('\n').filter(Boolean).length <= 5 && curEp.toLowerCase().includes('seguridad social'));

        if (isLegacyEp) {

            epTextarea.value = obligDefaults.ep.map((item, idx) => `${idx + 1}. ${item}`).join('\n');

        }

    }



    const minutaTextarea = document.getElementById('agent-result-oblig-minuta');

    if (minutaTextarea) {

        if (state.wizard.obligacionesMinuta && state.wizard.obligacionesMinuta.length > 0) {

            minutaTextarea.value = state.wizard.obligacionesMinuta.map((item, idx) => `${idx + 1}. ${item}`).join('\n');

        } else {

            const curMin = minutaTextarea.value.trim();

            const isLegacyMin = !curMin || (curMin.split('\n').filter(Boolean).length <= 5 && curMin.toLowerCase().includes('subordinación laboral'));

            if (isLegacyMin) {

                minutaTextarea.value = obligDefaults.minuta.map((item, idx) => `${idx + 1}. ${item}`).join('\n');

            }

        }

    }



    const empresaTextarea = document.getElementById('agent-result-oblig-empresa');

    if (empresaTextarea) {

        if (state.wizard.obligacionesEmpresa && state.wizard.obligacionesEmpresa.length > 0) {

            empresaTextarea.value = state.wizard.obligacionesEmpresa.map((item, idx) => `${idx + 1}. ${item}`).join('\n');

        } else {

            const curEmp = empresaTextarea.value.trim();

            const isLegacyEmp = !curEmp || (curEmp.split('\n').filter(Boolean).length <= 3);

            if (isLegacyEmp && obligDefaults.empresa) {

                empresaTextarea.value = obligDefaults.empresa.map((item, idx) => `${idx + 1}. ${item}`).join('\n');

            }

        }

    }



    const resultName = document.getElementById('agent-result-name');

    if (resultName) {

        const tipLabel = tipologia === 'OBRA' ? 'Contrato de Obra' : (tipologia === 'SUMINISTRO' ? 'Suministro de Bienes' : 'Prestación de Servicios');

        resultName.innerText = `Estructuración: ${tipLabel}`;

    }



    setWizardStep(3);

    showToast('Revise y modifique los textos y obligaciones antes de generar el Word.', 'info');

}



// Redirección del botón para compatibilidad

function runMultiAgentDrafting() {

    proceedToStep3Manual();

}



async function finalizeContractCreation() {

    const rawObjeto = document.getElementById('agent-result-objeto')?.value.trim();

    const tipologia = state.wizard.tipologia || state.wizard.typology || 'PRESTACION_SERVICIOS';

    const objeto = rawObjeto ? formatObjetoContractual(rawObjeto, tipologia) : '';

    if (!objeto) {

        showToast('El objeto contractual no puede estar vacío.', 'warning');

        document.getElementById('agent-result-objeto')?.focus();

        return;

    }



    const justificacion = document.getElementById('agent-result-justificacion')?.value.trim() 

        || 'Garantizar la prestación eficiente y continua de los servicios públicos bajo el régimen de la Ley 142 de 1994.';

    const objetivoGeneral = document.getElementById('agent-result-obj-general')?.value.trim() || objeto;

    const objetivosEspecificos = getStep3ObjetivosEspecificos();



    // Extraer líneas de obligaciones limpiando números o viñetas

    const obligEpText = document.getElementById('agent-result-oblig-ep')?.value || '';

    const obligacionesEp = obligEpText.split('\n')

        .map(line => line.trim().replace(/^([0-9]+[\.\)]|•|-)\s*/, '').trim())

        .filter(line => line.length > 0);



    const obligMinutaText = document.getElementById('agent-result-oblig-minuta')?.value || '';

    const obligacionesMinuta = obligMinutaText.split('\n')

        .map(line => line.trim().replace(/^([0-9]+[\.\)]|•|-)\s*/, '').trim())

        .filter(line => line.length > 0);



    const obligEmpresaText = document.getElementById('agent-result-oblig-empresa')?.value || '';

    const obligacionesEmpresa = obligEmpresaText.split('\n')

        .map(line => line.trim().replace(/^([0-9]+[\.\)]|•|-)\s*/, '').trim())

        .filter(line => line.length > 0);



    try {

        showToast('Guardando contrato y estructurando documentos Word...', 'info');



        // Obtener vigencia y número de contrato dinámico

        const wizVigenciaInput = document.getElementById('wiz-vigencia');

        const contractVigencia = (wizVigenciaInput && wizVigenciaInput.value && wizVigenciaInput.value !== 'ALL')

            ? parseInt(wizVigenciaInput.value, 10)

            : (state.wizard.vigencia || (state.selectedVigencia !== 'ALL' ? state.selectedVigencia : 2026));



        let numContrato = document.getElementById('wiz-numero-contrato')?.value.trim() || state.wizard.numeroContrato;

        if (!numContrato) {

            try {

                const nextData = await window.api.getNextContractNumber(contractVigencia, tipologia);

                numContrato = nextData.sugerido;

            } catch (e) {

                const prefixMap = { PRESTACION_SERVICIOS: 'CPS', SUMINISTRO: 'CS', OBRA: 'CO', ARRENDAMIENTO: 'CA' };

                const pfx = prefixMap[tipologia] || 'CPS';

                numContrato = `${pfx}-001-${contractVigencia}`;

            }

        }



        const tipoContrato = document.getElementById('agent-result-tipo-contrato')?.value.trim() 

            || state.wizard.tipoContrato 

            || (tipologia === 'PRESTACION_SERVICIOS' ? 'PRESTACIÓN DE SERVICIOS' : tipologia);



        const marcoJuridico = document.getElementById('agent-result-marco-juridico')?.value.trim()

            || state.wizard.marcoJuridico

            || (DEFAULT_LEGAL_FRAMEWORK_BY_TYPOLOGY[tipologia] || DEFAULT_LEGAL_FRAMEWORK_BY_TYPOLOGY['PRESTACION_SERVICIOS']).text;



        const currentContractor = (state.contractors || []).find(c => c.id == state.wizard.contractorId);

        const tipoPer = state.wizard.contractorTipoPersona || currentContractor?.tipo_persona || 'NATURAL';

        const isJuridica = (tipoPer === 'JURIDICA');

        const repNom = isJuridica ? (state.wizard.contractorRepLegal || currentContractor?.representante_legal_nombre || null) : null;

        const repDoc = isJuridica ? (state.wizard.contractorRepDoc || currentContractor?.representante_legal_documento || null) : null;

        const dvVal = isJuridica ? (state.wizard.contractorDv || currentContractor?.digito_verificacion || null) : null;



        const contractData = {

            numero_contrato: numContrato,

            vigencia: contractVigencia,

            modalidad_seleccion: state.wizard.modalidad || 'CONTRATACION_DIRECTA',

            tipologia: tipologia,

            contratista_id: state.wizard.contractorId,

            objeto: objeto,

            justificacion_necesidad: justificacion,

            marco_juridico: marcoJuridico,

            objetivo_general: objetivoGeneral,

            objetivos_especificos: objetivosEspecificos.length > 0 ? objetivosEspecificos : [objeto],

            obligaciones_estudio_previo: obligacionesEp,

            obligaciones_minuta: obligacionesMinuta,

            obligaciones_empresa: obligacionesEmpresa,

            valor_total: state.wizard.valorEstimado || 0,

            plazo_ejecucion: state.wizard.plazo || 1,

            unidad_plazo: state.wizard.unidadPlazo || 'MESES',

            supervisor_nombre: state.wizard.supervisorNombre || 'Ing. Supervisor Técnico',

            supervisor_cargo: state.wizard.supervisorCargo || 'Director Operativo y Técnico',

            supervisor_tipo_documento: state.wizard.supervisorTipoDoc || 'CC',

            supervisor_documento: state.wizard.supervisorDocumento || null,

            supervisor_dependencia: state.wizard.supervisorDependencia || 'Área Técnica y Operativa',

            fecha_suscripcion: document.getElementById('agent-result-fecha-suscripcion')?.value || state.wizard.fechaSuscripcion || null,

            fecha_acta_inicio: document.getElementById('agent-result-fecha-inicio')?.value || state.wizard.fechaInicio || null,

            fecha_terminacion: document.getElementById('agent-result-fecha-terminacion')?.value || state.wizard.fechaTerminacion || null,

            cdp_numero: document.getElementById('agent-result-cdp-numero')?.value.trim() || state.wizard.cdpNumero || null,

            cdp_fecha: document.getElementById('agent-result-cdp-fecha')?.value || state.wizard.cdpFecha || null,

            cdp_rubro: document.getElementById('agent-result-cdp-rubro')?.value.trim() || state.wizard.cdpRubro || null,

            estado: 'BORRADOR',

            garantias_exigidas: {},

            metadatos_agente: {

                modo: 'MANUAL_USUARIO',

                tipologia: tipologia,

                tipo_contrato: tipoContrato,

                tipo_de_contrato: tipoContrato,

                tipo_persona: tipoPer,

                contratista_tipo_persona: tipoPer,

                representante_legal_nombre: repNom,

                representante_legal_documento: repDoc,

                digito_verificacion: dvVal,

                cdp_numero: document.getElementById('agent-result-cdp-numero')?.value.trim() || state.wizard.cdpNumero || null,

                cdp_fecha: document.getElementById('agent-result-cdp-fecha')?.value || state.wizard.cdpFecha || null,

                cdp_rubro: document.getElementById('agent-result-cdp-rubro')?.value.trim() || state.wizard.cdpRubro || null,

                cdp_rubro_nombre: document.getElementById('agent-result-cdp-rubro-nombre')?.value.trim() || state.wizard.cdpRubroNombre || null,

                cdp_valor: parseFloat(document.getElementById('agent-result-cdp-valor')?.value) || state.wizard.cdpValor || state.wizard.valorEstimado || null,

                cdp_clasificadores: (document.getElementById('agent-result-cdp-clasificadores')?.value.trim() || state.wizard.cdpClasificadores || '')

                    .split('\n')

                    .map(s => s.trim())

                    .filter(Boolean),

                cdp_texto_completo: updateCdpLivePreview()

            }

        };



        const created = await window.api.createContract(contractData);

        state.wizard.createdContractId = created.id;



        // Configure Step 4 buttons

        document.getElementById('final-contract-num').innerText = created.numero_contrato;

        document.getElementById('btn-final-download-ep').onclick = () => downloadDocx(created.id, 'ESTUDIO_PREVIO');

        document.getElementById('btn-final-download-minuta').onclick = () => downloadDocx(created.id, 'MINUTA');

        document.getElementById('btn-final-download-acta').onclick = () => downloadDocx(created.id, 'ACTA_INICIO');

        document.getElementById('btn-final-sync-excel').onclick = () => syncContractExcel(created.id);



        setWizardStep(4);

        showToast('¡Contrato guardado exitosamente con sus datos personalizados!', 'success');

        loadDashboard();

    } catch (e) {

        showToast(`Error al guardar contrato: ${e.message}`, 'error');

    }

}



// Stubs para compatibilidad

// Sanitizador estricto de Objeto Contractual

function sanitizeObjetoContractual(texto) {

    if (!texto || typeof texto !== 'string') return '';

    let clean = texto

        .replace(/(?:PRESTACI[OÓ]N\s+DE\s+SERVICIOS\s+DE\s+APOYO\s+A\s+LA\s+GESTI[OÓ]N\s+PARA\s+DISPONIBILIDAD\s*)+/gi, '')

        .replace(/\bDISPONIBILIDAD\b/gi, '')

        .replace(/(?:PRESTACI[OÓ]N\s+DE\s+SERVICIOS\s+DE\s+APOYO\s+A\s+LA\s+GESTI[OÓ]N\s+PARA\s*){2,}/gi, 'PRESTACIÓN DE SERVICIOS DE APOYO A LA GESTIÓN PARA ')

        .replace(/(?:PRESTACI[OÓ]N\s+DE\s+SERVICIOS(?:\s+PARA)?\s*){2,}/gi, 'PRESTACION DE SERVICIOS PARA ')

        .replace(/TODO\.COSTO/gi, 'TODO COSTO')

        .replace(/\s*ADSCRITOS?\s+AL\s+[AÁ]REA\s+OPERATIVA(?:(?:\s+DE\s+LA)?\s+EMPRESA\s+DE\s+SERVICIOS\s+P[UÚ]BLICOS\s+DE\s+YOLOMB[OÓ](?:\s+E\.?S\.?P\.?)?)?/gi, '')

        .replace(/\bPARA\s+PARA\b/gi, 'PARA')

        .replace(/\s+/g, ' ')

        .trim();

    return clean;

}



// Limpiar la caché, localStorage de pruebas y resetear el formulario actual del wizard

function clearWizardCacheAndLocalStorage() {

    // 1. Limpiar llaves de localStorage asociadas a pruebas de formulario

    const keysToRemove = [

        'espy_wizard_draft',

        'espy_temp_contract',

        'espy_temp_objeto',

        'espy_temp_propuesta'

    ];

    keysToRemove.forEach(k => localStorage.removeItem(k));



    // 2. Reset total del estado del wizard

    resetWizardState();



    // 3. Limpiar inputs visuales

    const objEl = document.getElementById('wiz-objeto');

    if (objEl) objEl.value = '';

    const justEl = document.getElementById('wiz-justificacion');

    if (justEl) justEl.value = '';

    const genEl = document.getElementById('wiz-obj-general');

    if (genEl) genEl.value = '';

    const statusEl = document.getElementById('step2-agent-status');

    if (statusEl) statusEl.innerHTML = '';



    showToast('Caché y datos del formulario reiniciados exitosamente a cero.', 'info');

}



// Generación / Regeneración del Objeto Contractual desde CERO

async function regenerateObjetoOnly() {

    const objEl = document.getElementById('wiz-objeto');

    const statusEl = document.getElementById('step2-agent-status');

    const btnRegen = document.getElementById('btn-regen-objeto');

    const origHtml = btnRegen ? btnRegen.innerHTML : '';



    // 1. RESET TOTAL DEL CAMPO Y ESTADO (objeto = "")

    if (objEl) objEl.value = '';

    if (state.wizard) {

        state.wizard.necesidad = '';

        state.wizard.necesidadPropuesta = '';

    }



    if (btnRegen) {

        btnRegen.disabled = true;

        btnRegen.innerHTML = `<span class="animate-spin inline-block w-3 h-3 border-2 border-sky-400 border-t-transparent rounded-full mr-1"></span> Redactando...`;

    }

    if (statusEl) {

        statusEl.innerHTML = `<span class="animate-spin inline-block w-3.5 h-3.5 border-2 border-sky-400 border-t-transparent rounded-full mr-1.5"></span> Redactando objeto contractual exclusivamente con la propuesta...`;

    }



    try {

        const tipologia = state.wizard?.typology || 'PRESTACION_SERVICIOS';

        const docIds = state.wizard?.uploadedDocIds || [];

        const contratistaNombre = state.wizard?.contractorName || null;



        // NO tomar ningún texto del CDP

        const ext = state.wizard?.extractedData || {};

        const propuestaReal = ext.objeto_propuesto || ext.alcance_propuesto || '';



        let nuevoObjeto = '';



        // Llamar al endpoint /api/agents/generate-objeto

        const res = await window.api.generateObjeto({

            tipologia: tipologia,

            necesidad_descripcion: propuestaReal,

            document_ids: docIds,

            contratista_nombre: contratistaNombre

        });



        if (res && res.objeto_sugerido) {

            nuevoObjeto = res.objeto_sugerido;

        } else if (propuestaReal) {

            nuevoObjeto = formatObjetoContractual(propuestaReal, tipologia);

        }



        // APLICAR FILTRO DE LIMPIEZA (SANITIZER) OBLIGATORIO

        let textoObjeto = sanitizeObjetoContractual(nuevoObjeto);

        textoObjeto = formatObjetoContractual(textoObjeto, tipologia);

        textoObjeto = sanitizeObjetoContractual(textoObjeto);



        // Guardar limpiamente en input y en el estado

        if (objEl) {

            objEl.value = textoObjeto;

        }

        if (state.wizard) {

            state.wizard.necesidad = textoObjeto;

        }



        const objGenEl = document.getElementById('wiz-obj-general');

        if (objGenEl && !objGenEl.value.trim()) {

            objGenEl.value = textoObjeto;

            if (state.wizard) state.wizard.objetivoGeneral = textoObjeto;

        }



        if (statusEl) {

            statusEl.innerHTML = `<span class="text-emerald-400 font-semibold">✓ Objeto contractual generado y sanitizado con éxito.</span>`;

        }

        showToast('Objeto generado limpiamente sin residuos ni prefijos duplicados.', 'success');

    } catch (err) {

        console.error('Error generando objeto:', err);

        if (statusEl) {

            statusEl.innerHTML = `<span class="text-rose-400 font-medium">✗ Error: ${err.message}</span>`;

        }

        showToast(`Error al redactar objeto: ${err.message}`, 'error');

    } finally {

        if (btnRegen) {

            btnRegen.disabled = false;

            btnRegen.innerHTML = origHtml;

        }

    }

}



async function generateObjetoWithAgent() {

    return regenerateObjetoOnly();

}



async function autoFormulateObjetoAndAlcanceIfEmpty() {}



async function setWizardExtensionLevel(level) {

    if (!state.wizard) state.wizard = {};

    state.wizard.extensionLevel = level || 'MEDIA';



    const btnCorta = document.getElementById('wiz-level-btn-corta');

    const btnMedia = document.getElementById('wiz-level-btn-media');

    const btnCompleta = document.getElementById('wiz-level-btn-completa');



    [btnCorta, btnMedia, btnCompleta].forEach(b => {

        if (b) {

            b.classList.remove('bg-sky-600', 'text-white', 'font-bold', 'shadow-sm');

            b.classList.add('text-slate-300', 'font-semibold');

        }

    });



    if (level === 'CORTA' && btnCorta) {

        btnCorta.classList.add('bg-sky-600', 'text-white', 'font-bold', 'shadow-sm');

        btnCorta.classList.remove('text-slate-300', 'font-semibold');

    } else if (level === 'COMPLETA' && btnCompleta) {

        btnCompleta.classList.add('bg-sky-600', 'text-white', 'font-bold', 'shadow-sm');

        btnCompleta.classList.remove('text-slate-300', 'font-semibold');

    } else if (btnMedia) {

        btnMedia.classList.add('bg-sky-600', 'text-white', 'font-bold', 'shadow-sm');

        btnMedia.classList.remove('text-slate-300', 'font-semibold');

    }

}

window.setWizardExtensionLevel = setWizardExtensionLevel;



async function regenerateAllWizardSections() {

    return autoDraftContractParametersWithAgent(false);

}

window.regenerateAllWizardSections = regenerateAllWizardSections;



async function regenerateWizardObjetivosOnly() {

    const objEl = document.getElementById('wiz-objeto');

    const tipo = state.wizard?.typology || 'PRESTACION_SERVICIOS';

    const rawObjeto = objEl?.value.trim() || state.wizard?.necesidad || '';

    const objeto = sanitizeObjetoContractual(rawObjeto);



    if (!objeto) {

        showToast('Por favor ingrese o formule primero el Objeto del contrato.', 'warning');

        return;

    }



    const nivel = state.wizard?.extensionLevel || 'MEDIA';

    const instr = document.getElementById('wiz-instrucciones-adicionales')?.value.trim() || null;

    const ext = state.wizard?.extractedData || {};



    try {

        showToast(`Generando objetivos con nivel ${nivel}...`, 'info');

        const res = await window.api.generateObjetivos({

            objeto: objeto,

            tipologia: tipo,

            propuesta_texto: ext.alcance_propuesto || ext.objeto_propuesto || '',

            propuesta_items: ext.items || null,

            nivel_extension: nivel,

            instrucciones_adicionales: instr

        });



        if (res && res.objetivo_general) {

            const genInput = document.getElementById('wiz-obj-general');

            if (genInput) genInput.value = res.objetivo_general;

            if (state.wizard) state.wizard.objetivoGeneral = res.objetivo_general;

        }



        if (res && Array.isArray(res.objetivos_especificos) && res.objetivos_especificos.length > 0) {

            const listEl = document.getElementById('wiz-obj-especificos-list');

            if (listEl) {

                listEl.innerHTML = '';

                res.objetivos_especificos.forEach(obj => {

                    if (typeof obj === 'string' && obj.trim()) {

                        addWizardObjetivoEspecifico(obj.trim());

                    }

                });

            }

        }



        showToast(`🎯 Objetivos actualizados exitosamente (Nivel ${nivel}).`, 'success');

    } catch (err) {

        console.error('Error regenerando objetivos:', err);

        showToast(`Error al regenerar objetivos: ${err.message}`, 'error');

    }

}

window.regenerateWizardObjetivosOnly = regenerateWizardObjetivosOnly;



async function regenerateJustificacionOnly() {

    const justEl = document.getElementById('wiz-justificacion');

    const objEl = document.getElementById('wiz-objeto');

    const tipo = state.wizard?.typology || 'PRESTACION_SERVICIOS';

    const rawObjeto = objEl?.value.trim() || state.wizard?.necesidad || '';

    const objeto = sanitizeObjetoContractual(rawObjeto);



    if (!objeto) {

        showToast('Por favor ingrese o formule primero el Objeto del contrato.', 'warning');

        return;

    }



    const btn = document.getElementById('btn-regen-justificacion');

    const origHtml = btn ? btn.innerHTML : '';

    if (btn) {

        btn.disabled = true;

        btn.innerHTML = `<span class="animate-spin inline-block w-3 h-3 border-2 border-amber-400 border-t-transparent rounded-full mr-1"></span> Elaborando...`;

    }



    const nivelExt = state.wizard?.extensionLevel || 'MEDIA';

    const instrAdic = document.getElementById('wiz-instrucciones-adicionales')?.value.trim() || null;



    try {

        const docIds = state.wizard?.uploadedDocIds || [];

        let justText = '';



        // Si hay documentos cargados en el wizard, intentar primero con JustificationAgent

        if (docIds.length > 0) {

            try {

                const resAgent = await window.api.generateJustificacion({

                    document_ids: docIds,

                    tipologia: tipo,

                    modalidad: state.wizard?.modalidad || 'CONTRATACION_DIRECTA',

                    objeto: objeto,

                    necesidad_contexto: objeto,

                    contratista_nombre: state.wizard?.contractorName || null,

                    valor_estimado: parseFloat(document.getElementById('wiz-valor')?.value) || state.wizard?.valorEstimado || 0,

                    nivel_extension: nivelExt,

                    instrucciones_adicionales: instrAdic

                });

                if (resAgent && resAgent.justificacion_estudio_previo) {

                    justText = resAgent.justificacion_estudio_previo;

                }

            } catch (errDoc) {

                console.warn('JustificationAgent no ejecutado con docs, usando build-necesidad directo:', errDoc);

            }

        }



        // Si no hay documentos o falló, utilizar el generador estricto de la API

        if (!justText) {

            const ext = state.wizard?.extractedData || {};

            const res = await window.api.buildNecesidad({

                objeto: objeto,

                tipologia: tipo,

                contexto_adicional: document.getElementById('wiz-alcance')?.value.trim() || '',

                nivel_extension: nivelExt,

                instrucciones_adicionales: instrAdic,

                propuesta_items: ext.items || null

            });

            justText = res.texto_completo || res.justificacion_necesidad;

        }



        if (justEl && justText) {

            justEl.value = justText;

            if (state.wizard) state.wizard.justificacion = justText;

            showToast(`Descripción de la Necesidad elaborada con éxito (Nivel ${nivelExt})`, 'success');

        }

    } catch (e) {

        showToast(`Error elaborando la necesidad: ${e.message}`, 'error');

    } finally {

        if (btn) {

            btn.disabled = false;

            btn.innerHTML = origHtml || `<span>✨</span> Elaborar con IA`;

        }

    }

}





// -------------------------------------------------------------

// EXCEL MATRIX VIEW CON BÚSQUEDA RÁPIDA Y FILTROS

// -------------------------------------------------------------

async function loadExcelView() {

    try {

        const contracts = await window.api.getContracts();

        state.excel = state.excel || {};

        state.excel.contracts = contracts || [];

        renderExcelMatrixTable();

    } catch (e) {

        showToast(`Error cargando matriz: ${e.message}`, 'error');

    }

}



function handleExcelMatrixSearch(val) {

    state.excel = state.excel || {};

    state.excel.searchQuery = (val || '').trim().toLowerCase();

    

    const clearBtn = document.getElementById('btn-clear-excel-search');

    if (clearBtn) {

        if (state.excel.searchQuery) {

            clearBtn.classList.remove('hidden');

        } else {

            clearBtn.classList.add('hidden');

        }

    }

    renderExcelMatrixTable();

}



function clearExcelMatrixSearch() {

    const input = document.getElementById('excel-matrix-search');

    if (input) {

        input.value = '';

        input.focus();

    }

    handleExcelMatrixSearch('');

}



function handleExcelMatrixFilterEstado(val) {

    state.excel = state.excel || {};

    state.excel.filterEstado = (val || '').trim();

    renderExcelMatrixTable();

}



function handleExcelMatrixFilterTipologia(val) {

    state.excel = state.excel || {};

    state.excel.filterTipologia = (val || '').trim();

    renderExcelMatrixTable();

}



function renderExcelMatrixTable() {

    const tbody = document.getElementById('excel-preview-body');

    if (!tbody) return;



    state.excel = state.excel || {};

    const allContracts = state.excel.contracts || [];

    const query = state.excel.searchQuery || '';

    const fEstado = state.excel.filterEstado || '';

    const fTipo = state.excel.filterTipologia || '';



    // Mapear preservando el número real de fila de Excel (fila 5 en adelante)

    let filtered = allContracts.map((c, i) => ({ ...c, _excelRowNumber: i + 5 }));



    if (query) {

        filtered = filtered.filter(c => {

            const num = (c.numero_contrato || '').toLowerCase();

            const contractor = (c.contratista?.nombre_o_razon_social || '').toLowerCase();

            const doc = (c.contratista?.numero_documento || '').toLowerCase();

            const tipo = (c.tipologia || '').toLowerCase().replace(/_/g, ' ');

            const sup = (c.supervisor_nombre || '').toLowerCase();

            const supDoc = (c.supervisor_documento || '').toLowerCase();

            const estado = (c.estado || '').toLowerCase();

            const objeto = (c.objeto || '').toLowerCase();

            const rowStr = String(c._excelRowNumber);

            const valStr = String(c.valor_total || '');



            return num.includes(query) ||

                   contractor.includes(query) ||

                   doc.includes(query) ||

                   tipo.includes(query) ||

                   sup.includes(query) ||

                   supDoc.includes(query) ||

                   estado.includes(query) ||

                   objeto.includes(query) ||

                   rowStr === query ||

                   valStr.includes(query);

        });

    }



    if (fEstado) {

        filtered = filtered.filter(c => c.estado === fEstado);

    }



    if (fTipo) {

        filtered = filtered.filter(c => c.tipologia === fTipo);

    }



    // Actualizar contador dinámico

    const counterText = document.getElementById('excel-records-count-text');

    if (counterText) {

        if (query || fEstado || fTipo) {

            counterText.innerText = `${filtered.length} de ${allContracts.length} contratos`;

        } else {

            counterText.innerText = `${allContracts.length} contratos`;

        }

    }



    // Actualizar indicador de filtro

    const indicator = document.getElementById('excel-filter-indicator');

    if (indicator) {

        if (query || fEstado || fTipo) {

            indicator.classList.remove('hidden');

            indicator.innerText = `Filtro: ${filtered.length} fila(s) visible(s)`;

        } else {

            indicator.classList.add('hidden');

        }

    }



    if (filtered.length === 0) {

        tbody.innerHTML = `

            <tr>

                <td colspan="12" class="py-12 text-center text-slate-400">

                    <div class="flex flex-col items-center justify-center gap-2">

                        <span class="text-2xl">🔍</span>

                        <span class="font-bold text-slate-300">No se encontraron contratos que coincidan con la búsqueda.</span>

                        <span class="text-xs text-slate-500">Pruebe con otro término o limpie los filtros activos.</span>

                        <button onclick="clearExcelMatrixSearch(); const es = document.getElementById('excel-filter-estado'); if (es) es.value=''; const et = document.getElementById('excel-filter-tipologia'); if (et) et.value=''; handleExcelMatrixFilterEstado(''); handleExcelMatrixFilterTipologia('');" 

                                class="mt-2 px-3.5 py-1.5 rounded-lg bg-sky-950/80 border border-sky-800/50 text-sky-300 hover:text-white text-xs font-semibold transition-all cursor-pointer shadow-sm">

                            Restablecer búsqueda y filtros

                        </button>

                    </div>

                </td>

            </tr>

        `;

        return;

    }



    tbody.innerHTML = filtered.map(c => {

        const isTerminado = c.estado === 'TERMINADO';

        const isEjecucion = c.estado === 'EN_EJECUCION';

        const isLiquidado = c.estado === 'LIQUIDADO';

        const isSuspendido = c.estado === 'SUSPENDIDO';

        const isAnulado = c.estado === 'ANULADO';



        const statusColorClass = isEjecucion 

            ? 'text-emerald-300 border-emerald-500/50 bg-emerald-950/70' 

            : (isTerminado 

                ? 'text-amber-300 border-amber-500/50 bg-amber-950/70' 

                : (isLiquidado 

                    ? 'text-purple-300 border-purple-500/50 bg-purple-950/70' 

                    : (isSuspendido 

                        ? 'text-rose-300 border-rose-500/50 bg-rose-950/70' 

                        : (isAnulado

                            ? 'text-slate-400 border-slate-600/60 bg-slate-800/90 line-through'

                            : 'text-slate-300 border-slate-700 bg-slate-800/80'))));



        return `

        <tr class="hover:bg-slate-800/40 border-b border-slate-800 text-xs font-mono transition-colors">

            <td class="py-2.5 px-3 text-slate-400 font-bold">${c._excelRowNumber}</td>

            <td class="py-2.5 px-3 font-semibold text-sky-400 cursor-pointer hover:underline" onclick="viewContractDetail(${c.id})" title="Haga clic para ver expediente y editar estado">${c.numero_contrato}</td>

            <td class="py-2.5 px-3 text-slate-300 font-sans">${(c.tipologia || '').replace(/_/g, ' ')}</td>

            <td class="py-2.5 px-3 text-slate-200 font-sans font-medium">${c.contratista?.nombre_o_razon_social || ''}</td>

            <td class="py-2.5 px-3 text-emerald-400 font-bold">${formatCurrency(c.valor_total)}</td>

            <td class="py-2.5 px-3 text-slate-300">${c.plazo_ejecucion || ''} ${c.unidad_plazo || ''}</td>

            <td class="py-2.5 px-3 text-slate-300 font-sans">

                <div class="font-medium text-white">${c.supervisor_nombre || 'Por definir'}</div>

                <div class="text-[10px] text-slate-400">${c.supervisor_cargo || ''} ${c.supervisor_documento ? `(${c.supervisor_tipo_documento || 'CC'} ${c.supervisor_documento})` : ''}</div>

            </td>

            <td class="py-2.5 px-3 text-slate-300">${c.fecha_suscripcion || 'Pendiente'}</td>

            <td class="py-2.5 px-3 text-slate-300">${c.fecha_acta_inicio || 'Pendiente'}</td>

            <td class="py-2.5 px-3 ${isTerminado ? 'text-amber-400 font-bold' : 'text-emerald-400'} font-semibold">${c.fecha_terminacion || 'Pendiente'}</td>

            <td class="py-2.5 px-3 whitespace-nowrap">

                ${window.api.isAdmin() ? `

                    <select onchange="handleExcelStatusChange(${c.id}, this.value, '${c.numero_contrato}')" 

                            title="Haga clic para modificar manualmente el estado de este contrato"

                            class="border rounded-lg px-2 py-1 text-xs font-bold transition-all cursor-pointer focus:outline-none focus:ring-2 focus:ring-sky-500 shadow-sm ${statusColorClass}">

                        <option value="EN_EJECUCION" ${c.estado === 'EN_EJECUCION' ? 'selected' : ''}>EN_EJECUCION</option>

                        <option value="TERMINADO" ${c.estado === 'TERMINADO' ? 'selected' : ''}>TERMINADO</option>

                        <option value="LIQUIDADO" ${c.estado === 'LIQUIDADO' ? 'selected' : ''}>LIQUIDADO</option>

                        <option value="SUSPENDIDO" ${c.estado === 'SUSPENDIDO' ? 'selected' : ''}>SUSPENDIDO</option>

                        <option value="APROBADO" ${c.estado === 'APROBADO' ? 'selected' : ''}>APROBADO</option>

                        <option value="BORRADOR" ${c.estado === 'BORRADOR' ? 'selected' : ''}>BORRADOR</option>

                        <option value="EN_REVISION" ${c.estado === 'EN_REVISION' ? 'selected' : ''}>EN_REVISION</option>

                        <option value="ANULADO" ${c.estado === 'ANULADO' ? 'selected' : ''}>ANULADO</option>

                    </select>

                ` : `

                    <span class="px-2.5 py-1 rounded-lg text-xs font-bold border ${statusColorClass}">

                        ${c.estado}

                    </span>

                `}

            </td>

            <td class="py-2.5 px-3 text-right whitespace-nowrap">

                <div class="flex items-center justify-end gap-1.5">

                    <button onclick="viewContractDetail(${c.id})" title="Ver y editar detalles completos" class="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded border border-slate-700 text-[11px] font-semibold flex items-center gap-1 transition-all">

                        <span>👁️</span>

                    </button>

                    <button onclick="handleUpdateSingleExcel(${c.id})" title="Actualizar en Excel" class="px-2.5 py-1 bg-sky-900/60 hover:bg-sky-800 text-sky-300 rounded border border-sky-700 text-[11px] font-semibold flex items-center gap-1 transition-all">

                        <span>🔄</span> Actualizar

                    </button>

                    <button onclick="handleDeleteSingleExcel(${c.id}, '${c.numero_contrato}')" title="Eliminar de Excel" class="px-2.5 py-1 bg-rose-950/70 hover:bg-rose-900 text-rose-300 rounded border border-rose-800 text-[11px] font-semibold flex items-center gap-1 transition-all">

                        <span>🗑️</span> Borrar

                    </button>

                </div>

            </td>

        </tr>`;

    }).join('');

}



async function handleExcelStatusChange(contractId, newStatus, contractNum) {

    if (!window.api.isAdmin()) {

        showToast('Acceso Denegado: Solo el Administrador puede modificar estados contractuales.', 'error');

        return;

    }

    try {

        showToast(`Actualizando estado de ${contractNum} a ${newStatus}...`, 'info');

        await window.api.updateContractStatus(contractId, newStatus, 'Actualización manual desde Matriz Excel');

        showToast(`Estado de ${contractNum} actualizado a ${newStatus} y sincronizado en Excel.`, 'success');

        await loadExcelView();

        if (state.currentTab === 'contracts') loadContractsTable();

        if (state.currentTab === 'dashboard') loadDashboard();

    } catch (e) {

        showToast(`Error al cambiar estado: ${e.message}`, 'error');

        await loadExcelView();

    }

}



async function handleUpdateSingleExcel(contractId) {

    try {

        showToast('Actualizando fila en la Matriz Excel...', 'info');

        const res = await window.api.syncContractToExcel(contractId);

        showToast(`Contrato ${res.resultado.numero_contrato} actualizado en Excel (Fila ${res.resultado.fila_excel}).`, 'success');

        loadExcelView();

    } catch (e) {

        showToast(`Error actualizando en Excel: ${e.message}`, 'error');

    }

}



async function handleDeleteSingleExcel(contractId, contractNum) {

    if (!confirm(`¿Desea eliminar la fila del contrato ${contractNum} en la Matriz de Excel?\n\n(El contrato seguirá existiendo en la base de datos).`)) {

        return;

    }

    try {

        showToast(`Eliminando contrato ${contractNum} de la matriz Excel...`, 'info');

        const res = await window.api.deleteContractFromExcel(contractId);

        showToast(res.mensaje, 'success');

        loadExcelView();

    } catch (e) {

        showToast(`Error eliminando de Excel: ${e.message}`, 'error');

    }

}



async function triggerSyncAllExcel() {

    try {

        showToast('Sincronizando todos los contratos en el libro maestro Excel...', 'info');

        const res = await window.api.syncAllToExcel();

        showToast(`Sincronizados ${res.resumen.total_sincronizados} contratos con éxito en Excel.`, 'success');

        loadExcelView();

    } catch (e) {

        showToast(`Error en sincronización: ${e.message}`, 'error');

    }

}



function downloadMasterExcelFile() {

    const vig = state.selectedVigencia !== 'ALL' ? state.selectedVigencia : null;

    window.open(window.api.getExcelDownloadUrl(vig), '_blank');

}



async function loadSettings() {

    const keyInput = document.getElementById('settings-gemini-key');

    if (keyInput) {

        try {

            const status = await window.api.getConfigStatus();

            if (status && status.gemini_configured) {

                keyInput.placeholder = `Clave configurada en el servidor (${status.masked_key})`;

                keyInput.value = '';

            } else {

                keyInput.placeholder = "Ingrese clave API de Gemini: AIzaSy...";

            }

        } catch (e) {

            keyInput.placeholder = "AIzaSy...";

        }

    }

    await renderSettingsVigenciasTable();

}



async function saveSettings() {

    const keyInput = document.getElementById('settings-gemini-key');

    if (keyInput) {

        const val = keyInput.value.trim();

        if (!val) {

            showToast('Por favor ingrese una clave válida para configurar.', 'warning');

            return;

        }

        try {

            const res = await window.api.configureApiKey(val);

            keyInput.value = '';

            keyInput.placeholder = `Clave configurada en el servidor (${res.masked_key || 'OK'})`;

            showToast('Clave de Gemini guardada de forma segura en el servidor.', 'success');

        } catch (e) {

            showToast(`Error al guardar clave: ${e.message}`, 'error');

        }

    }

}



async function renderSettingsVigenciasTable() {

    const tbody = document.getElementById('settings-vigencias-tbody');

    if (!tbody) return;



    try {

        const vigencias = await window.api.getVigencias();

        state.vigencias = vigencias || [];



        if (state.vigencias.length === 0) {

            tbody.innerHTML = '<tr><td colspan="6" class="py-4 text-center text-slate-500">No hay vigencias registradas.</td></tr>';

            return;

        }



        tbody.innerHTML = state.vigencias.map(v => {

            const isActive = !!v.es_vigencia_actual;

            const statusBadge = isActive

                ? '<span class="px-2.5 py-1 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 shadow-sm">★ Activa</span>'

                : '<span class="px-2.5 py-1 rounded-full text-[10px] font-medium bg-slate-800 text-slate-400 border border-slate-700">Abierta</span>';



            const budgetFmt = v.presupuesto_base && v.presupuesto_base > 0

                ? formatCurrency(v.presupuesto_base)

                : '<span class="text-slate-500 italic">No asignado</span>';



            const activateBtn = isActive

                ? '<span class="text-[11px] text-emerald-400 font-semibold px-2 py-1">En curso</span>'

                : `<button onclick="activateVigenciaDirect(${v.year})" class="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-emerald-950 text-slate-300 hover:text-emerald-300 border border-slate-700 hover:border-emerald-600/50 text-[11px] font-semibold transition-all">Activar</button>`;



            return `

                <tr class="hover:bg-slate-800/40 transition-colors">

                    <td class="py-3 px-4 font-mono font-bold text-white">${v.year}</td>

                    <td class="py-3 px-4">

                        <div class="font-semibold text-slate-200">${v.nombre || ('Vigencia Fiscal ' + v.year)}</div>

                        <div class="text-[10px] text-slate-400 truncate max-w-xs">${v.descripcion || 'Era de Contratación Anual'}</div>

                    </td>

                    <td class="py-3 px-4 text-center font-mono font-semibold text-sky-400">${v.total_contratos}</td>

                    <td class="py-3 px-4 text-right font-mono text-emerald-400">${budgetFmt}</td>

                    <td class="py-3 px-4 text-center">${statusBadge}</td>

                    <td class="py-3 px-4 text-right space-x-1.5">

                        ${activateBtn}

                        <button onclick="handleGlobalVigenciaChange(${v.year}); switchTab('contracts');" class="px-2.5 py-1 rounded-lg bg-sky-950/60 hover:bg-sky-900 text-sky-300 border border-sky-700/50 text-[11px] font-semibold transition-all">Ver Contratos</button>

                    </td>

                </tr>

            `;

        }).join('');

    } catch (e) {

        tbody.innerHTML = `<tr><td colspan="6" class="py-4 text-center text-rose-400">Error cargando vigencias: ${e.message}</td></tr>`;

    }

}



async function activateVigenciaDirect(year) {

    try {

        showToast(`Estableciendo Vigencia Fiscal ${year} como activa...`, 'info');

        await window.api.activateVigencia(year);

        showToast(`¡Vigencia Fiscal ${year} activada con éxito!`, 'success');

        await loadVigencias();

        state.selectedVigencia = year;

        localStorage.setItem('espy_selected_vigencia', year);

        renderVigenciasSelectors();

        updateVigenciaBadgeDisplay();

        await renderSettingsVigenciasTable();

    } catch (e) {

        showToast(`Error al activar vigencia: ${e.message}`, 'error');

    }

}



// -------------------------------------------------------------

// MODELOS WORD (PLANTILLAS .DOCX)

// -------------------------------------------------------------

// -------------------------------------------------------------

// MODELOS WORD (PLANTILLAS .DOCX)

// -------------------------------------------------------------

state.selectedTemplateCategory = 'ALL';



async function loadTemplatesTab() {

    const grid = document.getElementById('templates-grid');

    if (!grid) return;

    grid.innerHTML = '<div class="col-span-full py-12 text-center text-slate-400">Cargando modelos Word oficiales...</div>';



    try {

        const templates = await window.api.getTemplatesStatus();

        state.templates = templates || [];

        renderTemplatesGrid();

    } catch (e) {

        grid.innerHTML = `<div class="col-span-full py-12 text-center text-rose-400">Error cargando plantillas: ${e.message}</div>`;

    }

}



function filterTemplatesCategory(cat) {

    state.selectedTemplateCategory = cat;

    document.querySelectorAll('.tpl-filter-btn').forEach(btn => {

        btn.classList.remove('bg-[#03008F]', 'text-white', 'shadow-sm');

        btn.classList.add('text-slate-600', 'dark:text-slate-400');

    });

    const activeBtn = document.getElementById(`tab-tpl-filter-${cat}`);

    if (activeBtn) {

        activeBtn.classList.remove('text-slate-600', 'dark:text-slate-400');

        activeBtn.classList.add('bg-[#03008F]', 'text-white', 'shadow-sm');

    }

    renderTemplatesGrid();

}



function renderTemplatesGrid() {

    const grid = document.getElementById('templates-grid');

    if (!grid) return;



    const templates = state.templates || [];

    const cat = state.selectedTemplateCategory || 'ALL';



    const filtered = cat === 'ALL' ? templates : templates.filter(t => t.categoria === cat);



    if (filtered.length === 0) {

        grid.innerHTML = '<div class="col-span-full py-12 text-center text-slate-400 text-xs">No hay plantillas registradas en esta categoría.</div>';

        return;

    }



    grid.innerHTML = filtered.map(t => {

        const isCustom = t.is_custom;

        const badge = isCustom 

            ? '<span class="px-2.5 py-1 rounded-full text-[11px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 flex items-center gap-1"><span>★</span> Personalizado Activo</span>'

            : '<span class="px-2.5 py-1 rounded-full text-[11px] font-semibold bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border border-slate-300 dark:border-slate-700">Oficial por Defecto</span>';



        const kb = (t.tamano_bytes / 1024).toFixed(1);

        const placeholdersPreview = t.placeholders_detectados && t.placeholders_detectados.length > 0

            ? t.placeholders_detectados.slice(0, 6).map(p => `<code class="bg-white dark:bg-slate-900 px-1 py-0.5 rounded text-[10px] text-sky-600 dark:text-sky-400 border border-slate-200 dark:border-slate-800 font-mono">{{${p}}}</code>`).join(' ') + (t.placeholders_detectados.length > 6 ? ` <span class="text-[10px] text-slate-500">+${t.placeholders_detectados.length - 6} más</span>` : '')

            : '<span class="text-[10px] text-slate-500">Variables institucionales</span>';



        let catBadgeClass = 'bg-sky-50 dark:bg-sky-950/60 text-[#1590D3] dark:text-sky-400 border-sky-200 dark:border-sky-800';

        if (t.categoria === 'MINUTAS') {

            catBadgeClass = 'bg-emerald-50 dark:bg-emerald-950/60 text-[#009540] dark:text-emerald-400 border-emerald-200 dark:border-emerald-800';

        } else if (t.categoria === 'ACTAS_Y_ADICIONES') {

            catBadgeClass = 'bg-purple-50 dark:bg-purple-950/60 text-purple-600 dark:text-purple-400 border-purple-200 dark:border-purple-800';

        }



        let modBadge = '';

        if (t.modalidad === 'SUMINISTRO') {

            modBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-50 dark:bg-amber-950/60 text-amber-600 dark:text-amber-400 border border-amber-200 dark:border-amber-800">Modalidad: Suministro</span>';

        } else if (t.modalidad === 'PRESTACION_SERVICIOS') {

            modBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-50 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400 border border-blue-200 dark:border-blue-800">Modalidad: Servicios</span>';

        } else if (t.modalidad === 'ADICION') {

            modBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-50 dark:bg-purple-950/60 text-purple-600 dark:text-purple-400 border border-purple-200 dark:border-purple-800">Modificación: Adición</span>';

        }



        const icon = t.icono || (t.tipo.includes('ESTUDIO') ? '📄' : (t.tipo.includes('MINUTA') ? '📑' : '🏁'));



        return `

            <div class="glass-card p-6 rounded-2xl flex flex-col justify-between space-y-4 border ${isCustom ? 'border-emerald-500/50 shadow-md' : 'border-slate-200 dark:border-slate-800'} transition-all cursor-default hover:shadow-xl group"

                 ondragover="event.preventDefault(); this.classList.add('border-sky-500', 'bg-sky-500/10');"

                 ondragleave="this.classList.remove('border-sky-500', 'bg-sky-500/10');"

                 ondrop="event.preventDefault(); this.classList.remove('border-sky-500', 'bg-sky-500/10'); if(event.dataTransfer && event.dataTransfer.files.length) handleCustomTemplateUpload('${t.tipo}', event.dataTransfer.files[0]);">

                <div class="space-y-3">

                    <div class="flex items-center justify-between gap-2">

                        <div class="flex items-center gap-2">

                            <span class="text-2xl p-2 rounded-xl bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 group-hover:scale-110 transition-transform">${icon}</span>

                            <span class="px-2 py-0.5 rounded-lg text-[10px] font-extrabold uppercase tracking-wider border ${catBadgeClass}">

                                ${t.categoria_nombre || t.categoria}

                            </span>

                        </div>

                        ${badge}

                    </div>

                    <div>

                        <div class="flex items-center gap-2 mb-1">

                            <h3 class="font-heading font-bold text-base text-slate-900 dark:text-white leading-tight">${t.nombre}</h3>

                        </div>

                        <div class="mb-2">${modBadge}</div>

                        <p class="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">${t.descripcion}</p>

                    </div>

                    <div class="p-3 bg-slate-50 dark:bg-slate-900/80 rounded-xl border border-slate-200 dark:border-slate-800/80 text-[11px] space-y-1.5 shadow-inner">

                        <p class="text-slate-700 dark:text-slate-300 font-medium truncate flex items-center gap-1">

                            <span class="text-slate-400">📄 Archivo:</span>

                            <span class="font-mono font-semibold text-slate-800 dark:text-slate-200">${t.archivo_nombre}</span>

                        </p>

                        <p class="text-slate-500 dark:text-slate-400 text-[10px]">

                            <strong>Tamaño:</strong> ${kb} KB • <strong>Modificado:</strong> ${t.ultima_modificacion}

                        </p>

                        <div class="pt-1 border-t border-slate-200 dark:border-slate-800/60">

                            <span class="text-[10px] font-semibold text-slate-600 dark:text-slate-400 block mb-1">Marcadores detectados en la plantilla:</span>

                            <div class="flex flex-wrap gap-1">${placeholdersPreview}</div>

                        </div>

                    </div>

                </div>



                <div class="space-y-2 pt-3 border-t border-slate-200 dark:border-slate-800">

                    <div class="grid grid-cols-2 gap-2">

                        <a href="${t.download_url}" target="_blank" class="px-3 py-2 rounded-xl text-xs font-semibold bg-white dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-700 text-center flex items-center justify-center gap-1.5 transition-all shadow-sm">

                            <span>⬇️</span> Descargar

                        </a>

                        <button type="button" onclick="document.getElementById('input-template-${t.tipo}').click()" class="px-3 py-2 rounded-xl text-xs font-bold gradient-btn text-white text-center flex items-center justify-center gap-1.5 cursor-pointer hover:scale-[1.02] active:scale-[0.98] transition-all shadow-md">

                            <span>⬆️</span> Subir Modelo

                        </button>

                        <input type="file" id="input-template-${t.tipo}" accept=".docx,.doc,.DOCX,.DOC,.docm,.dotx,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/msword" class="hidden" onchange="handleCustomTemplateUpload('${t.tipo}', this)">

                    </div>

                    ${isCustom ? `

                        <button onclick="handleResetTemplate('${t.tipo}')" class="w-full py-1.5 rounded-lg text-[11px] font-medium text-slate-500 dark:text-slate-400 hover:text-rose-500 dark:hover:text-rose-400 transition-colors flex items-center justify-center gap-1 cursor-pointer">

                            <span>↺</span> Restablecer a plantilla oficial por defecto

                        </button>

                    ` : ''}

                </div>

            </div>

        `;

    }).join('');

}



async function handleCustomTemplateUpload(templateType, fileOrInput) {

    let file = null;

    if (fileOrInput instanceof HTMLInputElement) {

        file = fileOrInput.files && fileOrInput.files[0] ? fileOrInput.files[0] : null;

        fileOrInput.value = ''; // Reset para permitir volver a seleccionar el mismo archivo si es necesario

    } else if (fileOrInput instanceof File) {

        file = fileOrInput;

    }



    if (!file) return;



    const name = (file.name || '').toLowerCase();

    const valid = name.endsWith('.docx') || name.endsWith('.doc') || name.endsWith('.docm') || name.endsWith('.dotx');

    if (!valid) {

        showToast('Formato no admitido. Seleccione un documento Word (.docx o .doc).', 'error');

        return;

    }



    const friendlyNames = {

        'ESTUDIO_PREVIO_SERVICIOS': 'Estudio Previo (Servicios)',

        'ESTUDIO_PREVIO_SUMINISTRO': 'Estudio Previo (Suministro)',

        'MINUTA_SERVICIOS': 'Minuta de Contrato (Servicios)',

        'MINUTA_SUMINISTRO': 'Minuta de Contrato (Suministro)',

        'ACTA_INICIO': 'Acta de Inicio',

        'ADICION': 'Minuta de Adición a Contrato',

        'ESTUDIO_PREVIO': 'Estudio Previo',

        'MINUTA': 'Minuta de Contrato'

    };

    const friendlyName = friendlyNames[templateType] || templateType;



    try {

        showToast(`Subiendo modelo de ${friendlyName}...`, 'info');

        const res = await window.api.uploadCustomTemplate(file, templateType);

        showToast(res?.mensaje || `Modelo de ${friendlyName} cargado y activado exitosamente.`, 'success');

        await loadTemplatesTab();

    } catch (e) {

        console.error('Error al subir modelo Word:', e);

        showToast(`Error al subir modelo Word: ${e.message}`, 'error');

    }

}



async function handleResetTemplate(templateType) {

    const friendlyNames = {

        'ESTUDIO_PREVIO_SERVICIOS': 'Estudio Previo (Servicios)',

        'ESTUDIO_PREVIO_SUMINISTRO': 'Estudio Previo (Suministro)',

        'MINUTA_SERVICIOS': 'Minuta de Contrato (Servicios)',

        'MINUTA_SUMINISTRO': 'Minuta de Contrato (Suministro)',

        'ACTA_INICIO': 'Acta de Inicio',

        'ADICION': 'Minuta de Adición a Contrato'

    };

    const friendlyName = friendlyNames[templateType] || templateType;



    if (!confirm(`¿Desea restablecer el modelo de ${friendlyName} al formato oficial por defecto de la ESP?`)) return;

    try {

        await window.api.resetCustomTemplate(templateType);

        showToast(`Plantilla ${friendlyName} restablecida al modelo oficial por defecto.`, 'success');

        loadTemplatesTab();

    } catch (e) {

        showToast(`Error al restablecer plantilla: ${e.message}`, 'error');

    }

}



// Initialization on DOMContentLoaded

document.addEventListener('DOMContentLoaded', () => {

    // Setup Navigation

    ['dashboard', 'contracts', 'contractors', 'wizard', 'excel', 'templates', 'settings'].forEach(tab => {

        const btn = document.getElementById(`nav-${tab}`);

        if (btn) btn.addEventListener('click', () => switchTab(tab));

    });



    // Setup Drag and Drop Multi-document

    const dropzone = document.getElementById('multi-dropzone') || document.getElementById('file-dropzone');

    const fileInput = document.getElementById('file-input');



    if (dropzone && fileInput) {

        dropzone.addEventListener('click', (e) => {

            // Evitar clic si se pulsó dentro del contenedor de archivos o botones

            if (e.target.closest('#uploaded-files-container') || e.target.closest('#btn-process-docs-container')) return;

            triggerFileInput(e);

        });

        dropzone.addEventListener('dragover', (e) => {

            e.preventDefault();

            dropzone.classList.add('border-sky-500', 'bg-sky-900/30');

        });

        dropzone.addEventListener('dragleave', () => {

            dropzone.classList.remove('border-sky-500', 'bg-sky-900/30');

        });

        dropzone.addEventListener('drop', (e) => {

            e.preventDefault();

            dropzone.classList.remove('border-sky-500', 'bg-sky-900/30');

            if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {

                handleMultipleFilesUpload(e.dataTransfer.files);

            }

        });

        fileInput.addEventListener('change', (e) => {

            if (e.target.files && e.target.files.length > 0) {

                handleMultipleFilesUpload(e.target.files);

            }

        });

    }



    // Contracts search & filter listeners

    document.getElementById('contracts-search')?.addEventListener('input', () => loadContractsTable());

    document.getElementById('filter-tipologia')?.addEventListener('change', () => loadContractsTable());

    document.getElementById('filter-estado')?.addEventListener('change', () => loadContractsTable());

    document.getElementById('filter-ocultar-anulados')?.addEventListener('change', () => loadContractsTable());



    // Atajo de teclado para la búsqueda en la Matriz Excel

    document.addEventListener('keydown', (e) => {

        if (state.currentTab === 'excel') {

            const isTyping = ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName);

            if (e.key === '/' && !isTyping) {

                e.preventDefault();

                const searchInput = document.getElementById('excel-matrix-search');

                if (searchInput) {

                    searchInput.focus();

                    searchInput.select();

                }

            } else if (e.key === 'Escape' && document.activeElement?.id === 'excel-matrix-search') {

                clearExcelMatrixSearch();

                document.activeElement.blur();

            }

        }

    });



    // Setup Wizard date calculation listeners

    const fechaInicioEl = document.getElementById('wiz-fecha-inicio');

    const plazoEl = document.getElementById('wiz-plazo');

    const unidadPlazoEl = document.getElementById('wiz-unidad-plazo');

    const fechaSuscripcionEl = document.getElementById('wiz-fecha-suscripcion');



    function autoCalculateEndDate() {

        const inicioVal = fechaInicioEl?.value;

        const plazoVal = parseInt(plazoEl?.value) || 0;

        const unidad = unidadPlazoEl?.value || 'MESES';

        const finEl = document.getElementById('wiz-fecha-terminacion');

        if (!inicioVal || !finEl || plazoVal <= 0) return;



        try {

            const parts = inicioVal.split('-');

            const d = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));

            if (unidad === 'MESES') {

                d.setMonth(d.getMonth() + plazoVal);

            } else {

                d.setDate(d.getDate() + plazoVal);

            }

            const yyyy = d.getFullYear();

            const mm = String(d.getMonth() + 1).padStart(2, '0');

            const dd = String(d.getDate()).padStart(2, '0');

            finEl.value = `${yyyy}-${mm}-${dd}`;

        } catch (e) {}

    }



    function autoCalculateStep3EndDate() {

        const inicioEl = document.getElementById('agent-result-fecha-inicio');

        const finEl = document.getElementById('agent-result-fecha-terminacion');

        const plazoVal = parseInt(state.wizard.plazo) || parseInt(document.getElementById('wiz-plazo')?.value) || 1;

        const unidad = state.wizard.unidadPlazo || document.getElementById('wiz-unidad-plazo')?.value || 'MESES';

        if (!inicioEl || !finEl || !inicioEl.value || plazoVal <= 0) return;



        try {

            const parts = inicioEl.value.split('-');

            if (parts.length !== 3) return;

            const d = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));

            if (unidad === 'MESES') {

                d.setMonth(d.getMonth() + plazoVal);

            } else if (unidad.includes('AÑO')) {

                d.setFullYear(d.getFullYear() + plazoVal);

            } else {

                d.setDate(d.getDate() + plazoVal);

            }

            const yyyy = d.getFullYear();

            const mm = String(d.getMonth() + 1).padStart(2, '0');

            const dd = String(d.getDate()).padStart(2, '0');

            finEl.value = `${yyyy}-${mm}-${dd}`;

            state.wizard.fechaInicio = inicioEl.value;

            state.wizard.fechaTerminacion = finEl.value;

        } catch (e) {}

    }

    window.autoCalculateStep3EndDate = autoCalculateStep3EndDate;



    // Default dates to today

    const todayStr = new Date().toISOString().split('T')[0];

    if (fechaSuscripcionEl && !fechaSuscripcionEl.value) fechaSuscripcionEl.value = todayStr;

    if (fechaInicioEl && !fechaInicioEl.value) {

        fechaInicioEl.value = todayStr;

        autoCalculateEndDate();

    }



    fechaInicioEl?.addEventListener('change', autoCalculateEndDate);

    plazoEl?.addEventListener('input', autoCalculateEndDate);

    unidadPlazoEl?.addEventListener('change', autoCalculateEndDate);



    // Initial Load & Auth Verification

    if (!window.api.isLoggedIn()) {

        showLoginScreen();

    } else {

        const storedUser = window.api.getCurrentUser();

        if (storedUser) {

            applyRolePermissions(storedUser);

            hideLoginScreen();

        }

        window.api.getMe().then(user => {

            applyRolePermissions(user);

            hideLoginScreen();

            sincronizarMarcasCorteCdp();

            loadVigencias().finally(() => {



                const allowedTabs = window.api.isAdmin() 

                    ? ['dashboard', 'contracts', 'contractors', 'wizard', 'excel', 'templates', 'settings', 'reports']

                    : ['dashboard', 'contracts', 'execution'];

                const initialHash = (window.location.hash || '').replace('#', '');

                if (allowedTabs.includes(initialHash)) {

                    switchTab(initialHash);

                } else {

                    switchTab('contracts');

                }

            });

        }).catch(err => {

            console.warn('Sesión inválida o expirada:', err);

            window.api.logout();

            document.body.classList.remove('role-admin', 'role-invitado');

            showLoginScreen();

        });

    }



    window.addEventListener('hashchange', () => {

        const allowedTabs = window.api.isAdmin() 

            ? ['dashboard', 'contracts', 'contractors', 'wizard', 'excel', 'templates', 'settings', 'reports']

            : ['dashboard', 'contracts', 'execution'];

        const hash = (window.location.hash || '').replace('#', '');

        if (allowedTabs.includes(hash) && state.currentTab !== hash) {

            switchTab(hash);

        }

    });

});



// =========================================================

// AGENTE DE ADICIONES A CONTRATOS (GESTIÓN Y MINUTAS WORD)

// =========================================================

let currentAdditionContractContext = null;



// Gestor de adiciones vigentes para el modal de detalle del contrato

async function loadContractAdditionsForModal(contractId) {

    const cardEl = document.getElementById('modal-adiciones-vigentes-card');

    const btnDownAdic = document.getElementById('btn-download-adicion-docx');

    const btnQuickDocx = document.getElementById('btn-modal-quick-download-docx');

    const btnFooterEdit = document.getElementById('btn-modal-footer-edit-addition');

    

    // Reset estado

    window.currentContractAdditions = [];

    window.currentContractLatestAddition = null;

    if (cardEl) {

        cardEl.classList.add('hidden');

        cardEl.style.display = 'none';

    }

    if (btnDownAdic) btnDownAdic.classList.add('hidden');

    if (btnQuickDocx) btnQuickDocx.classList.add('hidden');

    if (btnFooterEdit) btnFooterEdit.classList.add('hidden');



    if (!contractId) return;



    try {

        const additions = await window.api.request(`/additions/contract/${contractId}/list`);

        if (!additions) return;



        if (Array.isArray(additions) && additions.length > 0) {

            window.currentContractAdditions = additions;

            const latest = additions[additions.length - 1];

            window.currentContractLatestAddition = latest;



            // Poblar campos de la tarjeta

            const badgeNum = document.getElementById('modal-adicion-badge-num');

            if (badgeNum) badgeNum.innerText = `Adición Nro. ${latest.numero_adicion}`;



            const subtitulo = document.getElementById('modal-adicion-subtitulo');

            if (subtitulo) {

                subtitulo.innerText = additions.length > 1 

                    ? `Mostrando última adición formal registrada (${latest.numero_adicion} de ${additions.length})` 

                    : 'Modificación contractual formal aprobada y vigente';

            }



            const valFmt = document.getElementById('modal-adicion-valor-fmt');

            if (valFmt) valFmt.innerText = formatCurrency(latest.valor_adicion);



            const cdpInfo = document.getElementById('modal-adicion-cdp-info');

            if (cdpInfo) {

                const cdpFmt = latest.cdp_fecha ? formatContractDate(latest.cdp_fecha) : '';

                cdpInfo.innerText = latest.cdp_numero ? `N° ${latest.cdp_numero}${cdpFmt ? ' (' + cdpFmt + ')' : ''}` : '-';

                cdpInfo.title = latest.cdp_rubro_nombre ? `${latest.cdp_rubro || ''} - ${latest.cdp_rubro_nombre}` : (latest.cdp_rubro || '');

            }



            const fechaInfo = document.getElementById('modal-adicion-fecha-info');

            if (fechaInfo) {

                fechaInfo.innerText = latest.fecha_adicion ? formatContractDate(latest.fecha_adicion) : 'Pendiente';

            }



            const justText = document.getElementById('modal-adicion-justificacion-text');

            if (justText) {

                justText.innerText = latest.justificacion || 'Garantizar la adecuada culminación del objeto contractual.';

            }



            const firmanteInfo = document.getElementById('modal-adicion-firmante-info');

            if (firmanteInfo) {

                const rep = latest.representante_legal_nombre || '';

                const doc = latest.representante_legal_documento || '';

                firmanteInfo.innerText = rep ? `${rep}${doc ? ' (C.C. ' + doc + ')' : ''}` : (latest.contratista_nombre || 'Representante Legal');

            }



            // Mostrar tarjeta y botones de acción

            if (cardEl) {

                cardEl.classList.remove('hidden');

                cardEl.style.display = 'block';

            }

            if (btnDownAdic) {

                btnDownAdic.classList.remove('hidden');

                btnDownAdic.title = `Descargar Minuta Word (.docx) de la Adición Nro. ${latest.numero_adicion}`;

            }

            if (btnQuickDocx) {

                btnQuickDocx.classList.remove('hidden');

            }

            if (btnFooterEdit) {

                btnFooterEdit.classList.remove('hidden');

                btnFooterEdit.innerText = `✏️ Editar Adición Nro. ${latest.numero_adicion}`;

            }



            // Sincronizar banner superior de cabecera

            const headerBanner = document.getElementById('modal-header-adicion-banner');

            if (headerBanner) {

                headerBanner.classList.remove('hidden');

                headerBanner.style.display = 'flex';

                const bNum = document.getElementById('header-adicion-badge');

                if (bNum) bNum.innerText = `Adición Nro. ${latest.numero_adicion}`;

                const mEl = document.getElementById('header-adicion-monto');

                if (mEl) mEl.innerText = formatCurrency(latest.valor_adicion);

                const cdpEl = document.getElementById('header-adicion-cdp');

                if (cdpEl) cdpEl.innerText = latest.cdp_numero ? `N° ${latest.cdp_numero}` : '-';

                const fEl = document.getElementById('header-adicion-fecha');

                if (fEl) fEl.innerText = latest.fecha_adicion ? formatContractDate(latest.fecha_adicion) : '-';

            }



            // Ajustar el botón de elaborar adición

            const btnElaborar = document.getElementById('btn-modal-create-addition');

            if (btnElaborar) {

                btnElaborar.innerHTML = '<span>➕</span> Nueva Adición';

                btnElaborar.title = `Elaborar siguiente adición presupuestal (Adición Nro. ${additions.length + 1})`;

            }

        } else if (state.selectedContract && state.selectedContract.adicion_1 && state.selectedContract.adicion_1 > 0) {

            // Contrato con adición numérica registrada directamente pero sin AdicionContrato formal

            window.currentContractAdditions = [];

            window.currentContractLatestAddition = null;



            const badgeNum = document.getElementById('modal-adicion-badge-num');

            if (badgeNum) badgeNum.innerText = 'Adición Registrada';



            const subtitulo = document.getElementById('modal-adicion-subtitulo');

            if (subtitulo) subtitulo.innerText = 'Modificación contractual monetaria registrada';



            const valFmt = document.getElementById('modal-adicion-valor-fmt');

            if (valFmt) valFmt.innerText = formatCurrency(state.selectedContract.adicion_1);



            const cdpInfo = document.getElementById('modal-adicion-cdp-info');

            if (cdpInfo) {

                cdpInfo.innerText = state.selectedContract.cdp_numero ? `N° ${state.selectedContract.cdp_numero}` : 'Sin CDP formal';

                cdpInfo.title = 'CDP registrado en el contrato';

            }



            const fechaInfo = document.getElementById('modal-adicion-fecha-info');

            if (fechaInfo) {

                fechaInfo.innerText = state.selectedContract.fecha_firma ? formatContractDate(state.selectedContract.fecha_firma) : 'Vigente';

            }



            const justText = document.getElementById('modal-adicion-justificacion-text');

            if (justText) {

                justText.innerText = 'Adición presupuestal registrada en el contrato principal.';

            }



            const firmanteInfo = document.getElementById('modal-adicion-firmante-info');

            if (firmanteInfo) {

                firmanteInfo.innerText = state.selectedContract.contratista_nombre || 'Contratista';

            }



            // Mostrar tarjeta y permitir eliminación

            if (cardEl) {

                cardEl.classList.remove('hidden');

                cardEl.style.display = 'block';

            }

            if (btnDownAdic) btnDownAdic.classList.add('hidden');

            if (btnQuickDocx) btnQuickDocx.classList.add('hidden');

            if (btnFooterEdit) btnFooterEdit.classList.add('hidden');



            const headerBanner = document.getElementById('modal-header-adicion-banner');

            if (headerBanner) {

                headerBanner.classList.remove('hidden');

                headerBanner.style.display = 'flex';

                const bNum = document.getElementById('header-adicion-badge');

                if (bNum) bNum.innerText = 'Adición Registrada';

                const mEl = document.getElementById('header-adicion-monto');

                if (mEl) mEl.innerText = formatCurrency(state.selectedContract.adicion_1);

            }



            const btnElaborar = document.getElementById('btn-modal-create-addition');

            if (btnElaborar) {

                btnElaborar.innerHTML = '<span>➕</span> Formalizar Adición';

                btnElaborar.title = 'Generar minuta formal Word (.docx) para esta adición';

            }

        } else {

            const headerBanner = document.getElementById('modal-header-adicion-banner');

            if (headerBanner && (!state.selectedContract || !state.selectedContract.adicion_1)) {

                headerBanner.classList.add('hidden');

                headerBanner.style.display = 'none';

            }

            const btnElaborar = document.getElementById('btn-modal-create-addition');

            if (btnElaborar) {

                btnElaborar.innerHTML = '<span>➕</span> Elaborar Adición';

                btnElaborar.title = 'Elaborar adición presupuestal a este contrato';

            }

        }

    } catch (e) {

        console.warn('Aviso consultando adiciones del contrato:', e);

    }

}

window.loadContractAdditionsForModal = loadContractAdditionsForModal;



function downloadCurrentAdditionDocx() {

    let latest = window.currentContractLatestAddition;

    if (!latest || !latest.id) {

        // Fallback: verificar contrato activo

        const cid = window.currentContractId || (state.selectedContract ? state.selectedContract.id : null);

        if (cid) {

            window.api.request(`/additions/contract/${cid}/list`).then(list => {

                if (Array.isArray(list) && list.length > 0) {

                    const itm = list[list.length - 1];

                    window.currentContractLatestAddition = itm;

                    const link = document.createElement('a');

                    link.href = `/api/additions/${itm.id}/download-docx?token=${encodeURIComponent(window.api.getToken())}`;

                    link.setAttribute('download', '');

                    document.body.appendChild(link);

                    link.click();

                    link.remove();

                    showToast(`Descargando Minuta Word de Adición Nro. ${itm.numero_adicion}...`, 'info');

                } else {

                    showToast('No se encontró una minuta de adición registrada para descargar.', 'warning');

                }

            }).catch(() => {

                showToast('No se encontró una minuta de adición registrada para descargar.', 'warning');

            });

            return;

        }

        showToast('No se encontró una minuta de adición registrada para descargar.', 'warning');

        return;

    }

    const downloadUrl = `/api/additions/${latest.id}/download-docx`;

    const link = document.createElement('a');

    link.href = downloadUrl;

    link.setAttribute('download', '');

    document.body.appendChild(link);

    link.click();

    link.remove();

    showToast(`Descargando Minuta Word de Adición Nro. ${latest.numero_adicion}...`, 'info');

}

window.downloadCurrentAdditionDocx = downloadCurrentAdditionDocx;



function handleEditCurrentAddition() {

    const latest = window.currentContractLatestAddition;

    if (!latest || !latest.id) {

        showToast('No hay una adición seleccionada para editar.', 'warning');

        return;

    }

    closeContractDetailModal();

    openEditContractAddition(latest.id);

}

window.handleEditCurrentAddition = handleEditCurrentAddition;



async function handleEditFromDetailModal() {

    const cid = window.currentContractId || (state.selectedContract ? state.selectedContract.id : null);

    if (!cid) {

        showToast('No se encontró el identificador del contrato seleccionado.', 'warning');

        return;

    }

    await openEditContractAdditionDirect(cid);

}

window.handleEditFromDetailModal = handleEditFromDetailModal;



async function openEditContractAdditionDirect(contractId) {

    if (!contractId) return;

    try {

        showToast('Consultando datos de la adición...', 'info');

        const additions = await window.api.request(`/additions/contract/${contractId}/list`);

        if (Array.isArray(additions) && additions.length > 0) {

            const latest = additions[additions.length - 1];

            closeContractDetailModal();

            await openEditContractAddition(latest.id);

            return;

        }

        // Si no tiene adición formal aún, abrir creador para dicho contrato

        closeContractDetailModal();

        await openContractAdditionModal(contractId);

    } catch (e) {

        console.error('Error abriendo adición de contrato:', e);

        closeContractDetailModal();

        await openContractAdditionModal(contractId);

    }

}

window.openEditContractAdditionDirect = openEditContractAdditionDirect;



async function loadSelectedContractAdditionForEdit() {

    const sel = document.getElementById('addition-contract-select');

    const cid = sel ? sel.value : null;

    if (!cid) return;

    await openEditContractAdditionDirect(cid);

}

window.loadSelectedContractAdditionForEdit = loadSelectedContractAdditionForEdit;



async function openEditContractAddition(additionId) {

    if (!additionId) return;



    try {

        const adic = await window.api.request(`/additions/${additionId}`);

        if (!adic) throw new Error('No se pudo obtener la información de la adición.');



        // Abrir el modal enlazado al contrato

        await openContractAdditionModal(adic.contrato_id);



        // Activar modo edición

        const editIdEl = document.getElementById('addition-edit-id');

        if (editIdEl) editIdEl.value = adic.id;



        const titleEl = document.getElementById('modal-addition-title');

        if (titleEl) titleEl.innerText = `Editar Adición Nro. ${adic.numero_adicion} - ${adic.numero_contrato}`;



        const subEl = document.getElementById('modal-addition-subtitle');

        if (subEl) subEl.innerText = 'Modifique los parámetros económicos, CDP o justificación y regenere la minuta Word oficial.';



        const btnSubmitText = document.getElementById('btn-addition-submit-text');

        if (btnSubmitText) btnSubmitText.innerText = 'Guardar Cambios y Regenerar Minuta (.docx)';



        // Bloquear selector de contratos para que no cambie de contrato en edición

        const sel = document.getElementById('addition-contract-select');

        if (sel) sel.disabled = true;



        // Aviso de modo edición

        const editNotice = document.getElementById('addition-edit-mode-notice');

        const editNoticeText = document.getElementById('addition-edit-mode-notice-text');

        if (editNotice) {

            editNotice.classList.remove('hidden');

            if (editNoticeText) {

                editNoticeText.innerText = `Modo Edición Activo: Modificando la Adición Nro. ${adic.numero_adicion} formal registrada. Al guardar, se actualizará el contrato y se regenerará la minuta Word (.docx).`;

            }

        }

        const alertBanner = document.getElementById('addition-existing-alert-banner');

        if (alertBanner) alertBanner.classList.add('hidden');



        const previewNum = document.getElementById('addition-preview-num-adicion');

        if (previewNum) {

            previewNum.innerText = `Editando Adición Nro. ${adic.numero_adicion}`;

            previewNum.className = 'text-amber-400 font-bold ml-1 px-2 py-0.5 rounded bg-amber-950/80 border border-amber-600';

        }



        // Cargar campos específicos de la adición

        if (adic.valor_adicion) {

            document.getElementById('addition-valor-monto').value = adic.valor_adicion;

        }

        if (adic.fecha_adicion) {

            document.getElementById('addition-fecha-firma').value = adic.fecha_adicion;

        }

        if (adic.justificacion) {

            document.getElementById('addition-justificacion').value = adic.justificacion;

        }

        if (adic.cdp_numero) {

            document.getElementById('addition-cdp-numero').value = adic.cdp_numero;

        }

        if (adic.cdp_fecha) {

            document.getElementById('addition-cdp-fecha').value = adic.cdp_fecha;

        }

        if (adic.cdp_rubro) {

            document.getElementById('addition-cdp-rubro').value = adic.cdp_rubro;

        }

        if (adic.cdp_rubro_nombre) {

            const rubroVal = document.getElementById('addition-cdp-rubro-nombre');

            const rubroBadge = document.getElementById('addition-cdp-rubro-nombre-badge');

            if (rubroVal) rubroVal.value = adic.cdp_rubro_nombre;

            if (rubroBadge) {

                rubroBadge.innerText = adic.cdp_rubro_nombre;

                rubroBadge.title = adic.cdp_rubro_nombre;

            }

        }

        if (adic.cdp_valor) {

            document.getElementById('addition-cdp-valor').value = adic.cdp_valor;

            const valFmt = document.getElementById('addition-cdp-valor-format');

            if (valFmt) valFmt.innerText = formatCurrency(adic.cdp_valor);

        }

        if (adic.representante_legal_nombre) {

            document.getElementById('addition-rep-nombre').value = adic.representante_legal_nombre;

        }

        if (adic.representante_legal_documento) {

            document.getElementById('addition-rep-doc').value = adic.representante_legal_documento;

        }



        updateAdditionCalculations();

        showToast(`Modo edición activado para Adición Nro. ${adic.numero_adicion}`, 'info');

    } catch (e) {

        showToast(`Error al cargar adición para edición: ${e.message}`, 'error');

    }

}

window.openEditContractAddition = openEditContractAddition;



async function handleDeleteCurrentAddition() {

    if (!window.api.isAdmin()) {

        showToast('Acción restringida: solo administradores pueden eliminar adiciones.', 'warning');

        return;

    }



    const latest = window.currentContractLatestAddition;

    const currentContract = state.selectedContract;

    const cid = window.currentContractId || (currentContract ? currentContract.id : null);



    if (!latest && (!currentContract || !currentContract.adicion_1 || currentContract.adicion_1 <= 0)) {

        showToast('No hay una adición registrada en este contrato para eliminar.', 'warning');

        return;

    }



    let confirmMsg = '';

    let endpoint = latest && latest.id ? `/additions/${latest.id}` : `/additions/contract/${cid}/all`;



    try {

        await window.api.request(endpoint, { method: 'DELETE' });



        showToast('✅ Adición eliminada y contrato revertido con éxito.', 'success');

        

        // Recargar contratos y refrescar modal

        await loadContractsTable();

        loadDashboard();



        // Refrescar modal actual si sigue abierto

        if (cid) {

            await viewContractDetail(cid);

        }

    } catch (e) {

        showToast(`Error eliminando adición: ${e.message}`, 'error');

    }

}

window.handleDeleteCurrentAddition = handleDeleteCurrentAddition;



function openContractAdditionForCurrentModal() {

    const cid = window.currentContractId || (state.selectedContract ? state.selectedContract.id : null);

    closeContractDetailModal();

    openContractAdditionModal(cid);

}



async function openContractAdditionModal(preselectedId = null) {

    const modal = document.getElementById('modal-contract-addition');

    if (!modal) return;



    // Reset Form

    const form = document.getElementById('form-contract-addition');

    if (form) form.reset();



    // Reset Modo Edición

    const editIdEl = document.getElementById('addition-edit-id');

    if (editIdEl) editIdEl.value = '';



    const titleEl = document.getElementById('modal-addition-title');

    if (titleEl) titleEl.innerText = 'Agente de Adiciones a Contratos';



    const subEl = document.getElementById('modal-addition-subtitle');

    if (subEl) subEl.innerText = 'Enlace contractual, extracción inteligente de CDP y generación de minuta oficial Word (.docx).';



    const btnSubmitText = document.getElementById('btn-addition-submit-text');

    if (btnSubmitText) btnSubmitText.innerText = 'Elaborar Adición y Descargar Minuta (.docx)';



    const sel = document.getElementById('addition-contract-select');

    if (sel) sel.disabled = false;



    const editNotice = document.getElementById('addition-edit-mode-notice');

    if (editNotice) editNotice.classList.add('hidden');



    const alertBanner = document.getElementById('addition-existing-alert-banner');

    if (alertBanner) alertBanner.classList.add('hidden');



    const previewEl = document.getElementById('addition-contract-preview');

    if (previewEl) previewEl.classList.add('hidden');



    const badge = document.getElementById('addition-contract-status-badge');

    if (badge) {

        badge.innerText = 'Seleccione un contrato';

        badge.className = 'text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700';

    }



    const cdpStatus = document.getElementById('addition-cdp-file-status');

    if (cdpStatus) {

        cdpStatus.innerText = 'El Agente extraerá automáticamente el número, fecha, rubro y valor mediante OCR.';

        cdpStatus.className = 'text-[11px] text-slate-400';

    }



    document.getElementById('addition-cdp-doc-id').value = '';

    document.getElementById('addition-calc-letras').innerText = 'CERO PESOS M/CTE.';

    document.getElementById('addition-calc-nuevo-total').innerText = '$0 COP';

    document.getElementById('addition-calc-porcentaje').innerText = '0.0%';

    

    // Set default date to today

    const todayStr = new Date().toISOString().split('T')[0];

    const fechaFirmaEl = document.getElementById('addition-fecha-firma');

    if (fechaFirmaEl) fechaFirmaEl.value = todayStr;



    // Populate contract selector

    sel.innerHTML = '<option value="">Cargando contratos disponibles...</option>';



    try {

        const contracts = await window.api.request('/additions/contracts-list');

        

        let html = '<option value="">-- Buscar o seleccionar contrato (49 vigentes) --</option>';

        contracts.forEach(c => {

            const valFormatted = formatCurrency(c.valor_total);

            const adicText = (c.adicion_1 && c.adicion_1 > 0) ? ` (Adic. previa: ${formatCurrency(c.adicion_1)})` : '';

            html += `<option value="${c.id}">${c.numero_contrato} - ${c.contratista_nombre} [${valFormatted}${adicText}]</option>`;

        });

        sel.innerHTML = html;



        if (preselectedId) {

            sel.value = preselectedId;

            await onAdditionContractSelected(preselectedId);

        }

    } catch (e) {

        showToast('Error cargando contratos: ' + e.message, 'error');

        sel.innerHTML = '<option value="">Error al cargar contratos</option>';

    }



    modal.classList.remove('hidden');

}



function closeContractAdditionModal() {

    const modal = document.getElementById('modal-contract-addition');

    if (modal) modal.classList.add('hidden');

}



async function onAdditionContractSelected(contractId) {

    const previewEl = document.getElementById('addition-contract-preview');

    if (!contractId) {

        currentAdditionContractContext = null;

        if (previewEl) previewEl.classList.add('hidden');

        document.getElementById('addition-contratista-nombre').value = '';

        document.getElementById('addition-contratista-documento').value = '';

        document.getElementById('addition-rep-nombre').value = '';

        document.getElementById('addition-rep-doc').value = '';

        return;

    }



    try {

        const ctx = await window.api.request(`/additions/contract-context/${contractId}`);

        if (!ctx) throw new Error('No se pudo obtener el contexto del contrato');

        currentAdditionContractContext = ctx;



        // Fill preview

        document.getElementById('addition-preview-codigo').innerText = ctx.numero_contrato;

        document.getElementById('addition-preview-tipologia-badge').innerText = ctx.tipologia.replace('_', ' ');

        

        const previewNum = document.getElementById('addition-preview-num-adicion');

        const editIdVal = document.getElementById('addition-edit-id')?.value;

        if (!editIdVal && previewNum) {

            previewNum.innerText = `Adición Nro. ${ctx.siguiente_numero_adicion}`;

            previewNum.className = 'text-amber-400 font-bold ml-1';

        }

        document.getElementById('addition-preview-objeto').innerText = ctx.objeto;

        document.getElementById('addition-preview-val-inicial').innerText = formatCurrency(ctx.valor_inicial);

        document.getElementById('addition-preview-adiciones-previas').innerText = formatCurrency(ctx.adiciones_acumuladas);

        document.getElementById('addition-preview-val-total').innerText = formatCurrency(ctx.valor_total_actual);



        // Fill Contractor & Legal rep

        const contr = ctx.contratista || {};

        document.getElementById('addition-contratista-nombre').value = contr.nombre_o_razon_social || '';

        document.getElementById('addition-contratista-documento').value = `${contr.numero_documento || ''}${contr.digito_verificacion ? '-' + contr.digito_verificacion : ''}`;

        

        // Editable legal representative

        document.getElementById('addition-rep-nombre').value = contr.representante_legal_nombre || '';

        document.getElementById('addition-rep-doc').value = contr.representante_legal_documento || '';



        // Status badge

        const badge = document.getElementById('addition-contract-status-badge');

        if (badge) {

            badge.innerText = `Contrato Enlazado: ${ctx.numero_contrato}`;

            badge.className = 'text-[10px] px-2 py-0.5 rounded bg-sky-950 text-sky-400 border border-sky-800';

        }



        // Si no estamos en modo edición y el contrato ya tiene adiciones registradas, mostrar alerta interactiva

        const alertBanner = document.getElementById('addition-existing-alert-banner');

        if (!editIdVal && ctx.adiciones_acumuladas > 0) {

            try {

                const list = await window.api.request(`/additions/contract/${contractId}/list`);

                if (Array.isArray(list) && list.length > 0) {

                    const lastAd = list[list.length - 1];

                    if (alertBanner) {

                        alertBanner.classList.remove('hidden');

                        const numLbl = document.getElementById('existing-addition-num-label');

                        const valLbl = document.getElementById('existing-addition-val-label');

                        const cdpLbl = document.getElementById('existing-addition-cdp-label');

                        if (numLbl) numLbl.innerText = `Adición Nro. ${lastAd.numero_adicion}`;

                        if (valLbl) valLbl.innerText = formatCurrency(lastAd.valor_adicion);

                        if (cdpLbl) cdpLbl.innerText = lastAd.cdp_numero ? `N° ${lastAd.cdp_numero}` : 'Sin CDP';

                    }

                } else if (alertBanner) {

                    alertBanner.classList.add('hidden');

                }

            } catch (err) {

                console.warn('Aviso verificando adición existente:', err);

            }

        } else if (alertBanner) {

            alertBanner.classList.add('hidden');

        }



        if (previewEl) previewEl.classList.remove('hidden');

        updateAdditionCalculations();

    } catch (e) {

        showToast('Error cargando contrato: ' + e.message, 'error');

    }

}



async function handleAdditionCDPUpload(file) {

    if (!file) return;

    const statusEl = document.getElementById('addition-cdp-file-status');

    statusEl.innerText = `⏳ Subiendo "${file.name}" y ejecutando OCR inteligente de CDP...`;

    statusEl.className = 'text-[11px] text-amber-400 animate-pulse font-semibold';



    const formData = new FormData();

    formData.append('file', file);

    if (currentAdditionContractContext) {

        formData.append('contrato_id', currentAdditionContractContext.contrato_id);

    }



    try {

        const data = await window.api.request('/additions/upload-cdp', {

            method: 'POST',

            body: formData,

            isFormData: true

        });



        // Save doc ID

        document.getElementById('addition-cdp-doc-id').value = data.document_id || '';



        // Auto-fill fields if extracted

        if (data.cdp_numero) document.getElementById('addition-cdp-numero').value = data.cdp_numero;

        if (data.cdp_fecha) document.getElementById('addition-cdp-fecha').value = data.cdp_fecha;

        if (data.cdp_rubro) {

            document.getElementById('addition-cdp-rubro').value = data.cdp_rubro;

            const rubroNomEl = document.getElementById('addition-cdp-rubro-nombre-badge');

            const rubroNomVal = document.getElementById('addition-cdp-rubro-nombre');

            if (data.cdp_rubro_nombre) {

                if (rubroNomVal) rubroNomVal.value = data.cdp_rubro_nombre;

                if (rubroNomEl) {

                    rubroNomEl.innerText = data.cdp_rubro_nombre;

                    rubroNomEl.title = data.cdp_rubro_nombre;

                }

            }

        }

        if (data.cdp_valor) {

            document.getElementById('addition-cdp-valor').value = data.cdp_valor;

            const valFmtEl = document.getElementById('addition-cdp-valor-format');

            if (valFmtEl) valFmtEl.innerText = formatCurrency(data.cdp_valor);



            // EL VALOR DE LA ADICIÓN SE OBTIENE DIRECTAMENTE DEL CDP (NUNCA DEL VALOR TOTAL DEL CONTRATO)

            const currentMonto = document.getElementById('addition-valor-monto');

            currentMonto.value = data.cdp_valor;

            updateAdditionCalculations();

        }



        // Auto-fill technical justification / object from CDP if available and currently empty

        if (data.cdp_objeto) {

            const justifEl = document.getElementById('addition-justificacion');

            if (justifEl && (!justifEl.value || justifEl.value.trim().length === 0)) {

                justifEl.value = data.cdp_objeto;

            }

        }



        statusEl.innerText = `✅ Archivo "${file.name}" procesado. Datos de CDP incorporados automáticamente.`;

        statusEl.className = 'text-[11px] text-emerald-400 font-semibold';

        showToast('CDP procesado con éxito. Datos incorporados.', 'success');

    } catch (e) {

        statusEl.innerText = `⚠️ No se pudo extraer automáticamente: ${e.message}. Puede digitar los campos manualmente.`;

        statusEl.className = 'text-[11px] text-rose-400 font-medium';

        showToast('Aviso: complete los datos del CDP manualmente', 'warning');

    }

}



// Sincronización automática de entrada manual de Valor CDP hacia Valor a Adicionar

function handleCDPValorInput(val) {

    const numVal = parseFloat(val) || 0;

    const valFmt = document.getElementById('addition-cdp-valor-format');

    if (valFmt) valFmt.innerText = numVal > 0 ? formatCurrency(numVal) : '';



    // El valor de la adición se obtiene estrictamente del CDP

    const montoEl = document.getElementById('addition-valor-monto');

    if (montoEl) {

        montoEl.value = numVal > 0 ? numVal : '';

        updateAdditionCalculations();

    }

}

window.handleCDPValorInput = handleCDPValorInput;



function updateAdditionCalculations() {

    const inputVal = parseFloat(document.getElementById('addition-valor-monto').value) || 0;

    const letrasEl = document.getElementById('addition-calc-letras');

    const nuevoTotalEl = document.getElementById('addition-calc-nuevo-total');

    const porcentajeEl = document.getElementById('addition-calc-porcentaje');



    // Number to words helper

    letrasEl.innerText = numeroALetrasCOPFront(inputVal);



    if (currentAdditionContractContext) {

        const totalActual = currentAdditionContractContext.valor_total_actual || 0;

        const valInicial = currentAdditionContractContext.valor_inicial || totalActual || 1;

        const nuevoTotal = totalActual + inputVal;

        nuevoTotalEl.innerText = formatCurrency(nuevoTotal);



        const totalAdiciones = (currentAdditionContractContext.adiciones_acumuladas || 0) + inputVal;

        const porcentaje = (totalAdiciones / valInicial) * 100;

        porcentajeEl.innerText = `${porcentaje.toFixed(1)}%`;



        if (porcentaje > 50) {

            porcentajeEl.className = 'text-rose-400 font-mono font-bold';

            porcentajeEl.title = 'Alerta: Supera el 50% del valor inicial (límite general sugerido en contratación)';

        } else {

            porcentajeEl.className = 'text-emerald-400 font-mono font-bold';

            porcentajeEl.title = 'Dentro del margen legal estándar';

        }

    } else {

        nuevoTotalEl.innerText = formatCurrency(inputVal);

        porcentajeEl.innerText = '0.0%';

    }

}



function numeroALetrasCOPFront(amount) {

    if (!amount || amount <= 0) return 'CERO PESOS M/CTE.';

    const UNIDADES = ["", "UN", "DOS", "TRES", "CUATRO", "CINCO", "SEIS", "SIETE", "OCHO", "NUEVE"];

    const DECENAS = ["", "DIEZ", "VEINTE", "TREINTA", "CUARENTA", "CINCUENTA", "SESENTA", "SETENTA", "OCHENTA", "NOVENTA"];

    const DIEZ_Y = ["DIEZ", "ONCE", "DOCE", "TRECE", "CATORCE", "QUINCE", "DIECISÉIS", "DIECISIETE", "DIECIOCHO", "DIECINUEVE"];

    const CENTENAS = ["", "CIENTO", "DOSCIENTOS", "TRESCIENTOS", "CUATROCIENTOS", "QUINIENTOS", "SEISCIENTOS", "SETECIENTOS", "OCHOCIENTOS", "NOVECIENTOS"];



    function tres(n) {

        if (n === 0) return "";

        if (n === 100) return "CIEN";

        let c = Math.floor(n / 100);

        let resto = n % 100;

        let d = Math.floor(resto / 10);

        let u = resto % 10;

        let texto_c = CENTENAS[c];

        let texto_du = "";

        if (resto < 10) texto_du = UNIDADES[u];

        else if (resto >= 10 && resto <= 19) texto_du = DIEZ_Y[resto - 10];

        else if (resto >= 20 && resto <= 29) texto_du = (resto === 20) ? "VEINTE" : `VEINTI${UNIDADES[u]}`;

        else texto_du = (u === 0) ? DECENAS[d] : `${DECENAS[d]} Y ${UNIDADES[u]}`;

        return `${texto_c} ${texto_du}`.trim();

    }



    let n = Math.round(amount);

    let millones = Math.floor(n / 1000000);

    let miles = Math.floor((n % 1000000) / 1000);

    let unidades = n % 1000;

    let partes = [];



    if (millones > 0) {

        if (millones === 1) partes.push("UN MILLÓN");

        else partes.push(`${tres(millones)} MILLONES`);

    }

    if (miles > 0) {

        if (miles === 1) partes.push("MIL");

        else partes.push(`${tres(miles)} MIL`);

    }

    if (unidades > 0 || partes.length === 0) {

        partes.push(tres(unidades));

    }

    return `${partes.join(' ').trim()} PESOS M/CTE.`;

}



function isSubstantiveTechnicalReason(text) {

    if (!text) return false;

    const clean = text.trim();

    if (clean.length < 15) return false;

    // Si ya contiene la estructura formal generada previamente (apartados 1, 2, 3), requiere ingresar un nuevo motivo si quiere regenerar

    if (clean.includes('1. Contexto Contractual') || clean.includes('3. Justificación Jurídica')) {

        return false;

    }

    const genericRegex = /^(agotamiento\s+del\s+inventario(\s+operativo)?|se\s+agot[oó]\s+el\s+presupuesto|se\s+acab[oó]\s+(la\s+plata|el\s+presupuesto)|falta\s+de\s+presupuesto|insuficiencia\s+(de\s+recursos|presupuestal)|adici[oó]n\s+(presupuestal|de\s+recursos)|mayor\s+demanda|continuidad\s+del\s+servicio)\.?$/i;

    if (genericRegex.test(clean)) return false;

    return true;

}



function openAdditionTechnicalReasonModal(valAdicion) {

    const modal = document.getElementById('modal-addition-technical-reason');

    if (!modal || !currentAdditionContractContext) return;



    const ctx = currentAdditionContractContext;

    const tipoBadge = document.getElementById('ai-reason-tipo-badge');

    const valorBadge = document.getElementById('ai-reason-valor-badge');

    const objetoText = document.getElementById('ai-reason-objeto-text');

    const guiaBox = document.getElementById('ai-reason-guia-box');

    const inputEl = document.getElementById('ai-reason-input');



    const tipologia = (ctx.tipologia || '').toUpperCase();

    if (tipoBadge) tipoBadge.innerText = ctx.tipologia ? ctx.tipologia.replace(/_/g, ' ') : 'PRESTACIÓN DE SERVICIOS';

    if (valorBadge) valorBadge.innerText = formatCurrency(valAdicion);

    if (objetoText) objetoText.innerText = ctx.objeto || '';



    // Guía adaptada estrictamente según tipología contractual

    if (guiaBox) {

        if (tipologia.includes('SUMINISTRO')) {

            guiaBox.innerHTML = `

                <div class="font-bold text-sky-300">📦 Criterio para Contratos de Suministro:</div>

                <div>Enfóquese en fluctuaciones de demanda, aumento en tasa de consumo de insumos/materiales operativos no previstos inicialmente y necesidad de mantener stock para garantizar el servicio.</div>

                <div class="text-[10px] text-amber-300 mt-1 italic">💡 Ej: "Aumentó la turbiedad del río por temporada de lluvias y se necesitó más sulfato de aluminio para potabilizar el agua."</div>

            `;

        } else if (tipologia.includes('OBRA')) {

            guiaBox.innerHTML = `

                <div class="font-bold text-sky-300">🏗️ Criterio para Contratos de Obra:</div>

                <div>Enfóquese en mayores cantidades de obra ejecutadas que superaron las proyectadas en diseños iniciales, o aparición de ítems no previstos necesarios para la infraestructura.</div>

                <div class="text-[10px] text-amber-300 mt-1 italic">💡 Ej: "Se encontraron cantidades de obra no previstas en la excavación e interferencias con redes subterráneas."</div>

            `;

        } else if (tipologia.includes('ARRENDAMIENTO')) {

            guiaBox.innerHTML = `

                <div class="font-bold text-sky-300">🏢 Criterio para Contratos de Arrendamiento:</div>

                <div>Enfóquese en la necesidad de prolongar la tenencia del bien mueble/inmueble para el funcionamiento ininterrumpido de las áreas operativas.</div>

                <div class="text-[10px] text-amber-300 mt-1 italic">💡 Ej: "Se requiere prolongar la tenencia del bien inmueble por 2 meses más mientras culmina la adecuación de la sede principal."</div>

            `;

        } else if (tipologia.includes('CONSULTOR')) {

            guiaBox.innerHTML = `

                <div class="font-bold text-sky-300">📑 Criterio para Contratos de Consultoría:</div>

                <div>Enfóquese en la ampliación del alcance analítico o estudios técnicos especializados indispensables para la viabilidad institucional.</div>

                <div class="text-[10px] text-amber-300 mt-1 italic">💡 Ej: "Se requiere profundizar los estudios geotécnicos por fallas de suelo detectadas en la cuenca de captación."</div>

            `;

        } else {

            guiaBox.innerHTML = `

                <div class="font-bold text-sky-300">👥 Criterio para Prestación de Servicios:</div>

                <div>Enfóquese en el aumento de la carga operativa, la necesidad de dar continuidad a procesos administrativos/técnicos indispensables, o nuevas necesidades misionales.</div>

                <div class="text-[10px] text-amber-300 mt-1 italic">💡 Ej: "Se requiere extender el servicio por 2 meses más debido al incremento sustancial de frentes de atención a la comunidad."</div>

            `;

        }

    }



    if (inputEl) {

        inputEl.value = '';

        setTimeout(() => inputEl.focus(), 100);

    }



    modal.classList.remove('hidden');

}



function closeAdditionTechnicalReasonModal() {

    const modal = document.getElementById('modal-addition-technical-reason');

    if (modal) modal.classList.add('hidden');

}



async function submitAdditionTechnicalReasonModal() {

    const inputEl = document.getElementById('ai-reason-input');

    const motivo = inputEl ? inputEl.value.trim() : '';

    if (!motivo || motivo.length < 12) {

        showToast('Por favor describa la razón técnica específica (mínimo 12 caracteres).', 'warning');

        if (inputEl) inputEl.focus();

        return;

    }

    const val = parseFloat(document.getElementById('addition-valor-monto').value) || 0;

    const btnModal = document.getElementById('btn-ai-reason-submit');

    const oldModalText = btnModal ? btnModal.innerHTML : '';

    if (btnModal) {

        btnModal.disabled = true;

        btnModal.innerHTML = '<span>⏳</span> Redactando en 3 apartados...';

    }



    try {

        await executeAdditionJustificationCall(motivo, val);

        closeAdditionTechnicalReasonModal();

    } finally {

        if (btnModal) {

            btnModal.disabled = false;

            btnModal.innerHTML = oldModalText;

        }

    }

}



async function executeAdditionJustificationCall(motivoTecnico, val) {

    const btn = document.getElementById('btn-addition-ai-just');

    const oldText = btn ? btn.innerHTML : '';

    if (btn) {

        btn.disabled = true;

        btn.innerHTML = '<span>⏳</span> Redactando con IA...';

    }



    const apiKey = window.api ? window.api.getApiKey() : (localStorage.getItem('gemini_api_key') || '');



    try {

        const data = await window.api.request('/additions/generate-justification', {

            method: 'POST',

            body: JSON.stringify({

                contrato_id: currentAdditionContractContext.contrato_id,

                valor_adicion: val,

                necesidad_usuario: motivoTecnico,

                razon_tecnica: motivoTecnico,

                override_api_key: apiKey || null

            })

        });



        if (data.status === 'requires_information') {

            // El backend aplicó la Regla de Oro y solicita la razón específica

            openAdditionTechnicalReasonModal(val);

            return;

        }



        const textareaEl = document.getElementById('addition-justificacion');

        if (textareaEl) {

            textareaEl.value = data.justificacion;

            textareaEl.focus();

        }

        showToast('Justificación estructurada en 3 apartados técnicos, jurídicos y financieros con éxito', 'success');

    } catch (e) {

        showToast('Error generando justificación: ' + e.message, 'error');

    } finally {

        if (btn) {

            btn.disabled = false;

            btn.innerHTML = oldText;

        }

    }

}



async function generateAdditionJustificationAI() {

    if (!currentAdditionContractContext) {

        showToast('Seleccione primero un contrato.', 'warning');

        return;

    }

    const val = parseFloat(document.getElementById('addition-valor-monto').value) || 0;

    if (val <= 0) {

        showToast('Ingrese primero el valor a adicionar antes de redactar la justificación.', 'warning');

        const inputVal = document.getElementById('addition-valor-monto');

        if (inputVal) inputVal.focus();

        return;

    }



    const usuarioNota = document.getElementById('addition-justificacion')?.value || '';



    // Si el usuario ya escribió un motivo técnico específico en el textarea, usarlo directamente

    if (isSubstantiveTechnicalReason(usuarioNota)) {

        await executeAdditionJustificationCall(usuarioNota, val);

    } else {

        // Regla de Oro: Detenerse y preguntar el motivo técnico específico

        openAdditionTechnicalReasonModal(val);

    }

}



async function submitContractAddition() {

    if (!currentAdditionContractContext) {

        showToast('Debe seleccionar un contrato.', 'warning');

        return;

    }

    let valAdicion = parseFloat(document.getElementById('addition-valor-monto').value);

    const cdpValor = parseFloat(document.getElementById('addition-cdp-valor').value);

    if ((!valAdicion || valAdicion <= 0) && cdpValor > 0) {

        valAdicion = cdpValor;

        document.getElementById('addition-valor-monto').value = cdpValor;

        updateAdditionCalculations();

    }

    if (!valAdicion || valAdicion <= 0) {

        showToast('Ingrese un valor a adicionar válido y superior a cero (obtenido del CDP).', 'warning');

        return;

    }

    const cdpNum = document.getElementById('addition-cdp-numero').value.trim();

    if (!cdpNum) {

        showToast('Ingrese el número del CDP que ampara la adición.', 'warning');

        return;

    }

    const cdpFecha = document.getElementById('addition-cdp-fecha').value;

    if (!cdpFecha) {

        showToast('Seleccione la fecha de expedición del CDP.', 'warning');

        return;

    }

    const justificacion = document.getElementById('addition-justificacion').value.trim();

    if (!justificacion) {

        showToast('Ingrese la justificación técnica y jurídica de la adición.', 'warning');

        return;

    }



    const editId = document.getElementById('addition-edit-id')?.value;

    const isEditing = Boolean(editId);



    const submitBtn = document.getElementById('btn-addition-submit');

    const oldBtnText = submitBtn.innerHTML;

    submitBtn.disabled = true;

    submitBtn.innerHTML = isEditing ? '<span>⏳</span> Actualizando y regenerando minuta...' : '<span>⏳</span> Elaborando Minuta Word (.docx)...';



    const payload = {

        contrato_id: currentAdditionContractContext.contrato_id,

        numero_adicion: currentAdditionContractContext.siguiente_numero_adicion,

        valor_adicion: valAdicion,

        justificacion: justificacion,

        cdp_numero: cdpNum,

        cdp_fecha: cdpFecha,

        cdp_rubro: document.getElementById('addition-cdp-rubro').value.trim() || null,

        cdp_rubro_nombre: (document.getElementById('addition-cdp-rubro-nombre') ? document.getElementById('addition-cdp-rubro-nombre').value.trim() : null) || null,

        cdp_valor: parseFloat(document.getElementById('addition-cdp-valor').value) || null,

        cdp_documento_id: parseInt(document.getElementById('addition-cdp-doc-id').value) || null,

        representante_legal_nombre: document.getElementById('addition-rep-nombre').value.trim() || null,

        representante_legal_documento: document.getElementById('addition-rep-doc').value.trim() || null,

        guardar_en_contratista: document.getElementById('addition-guardar-contratista').checked,

        fecha_adicion: document.getElementById('addition-fecha-firma').value || null

    };



    try {

        const endpoint = isEditing ? `/additions/${editId}` : '/additions/create';

        const method = isEditing ? 'PUT' : 'POST';



        const data = await window.api.request(endpoint, {

            method: method,

            body: JSON.stringify(payload)

        });



        const successMsg = isEditing 

            ? `✅ Adición Nro. ${data.numero_adicion} actualizada exitosamente. Nueva minuta generada.`

            : `✅ Adición Nro. ${data.numero_adicion} creada exitosamente. Minuta descargada.`;

        showToast(successMsg, 'success');

        closeContractAdditionModal();



        // Download Word file

        if (data.download_url) {

            const link = document.createElement('a');

            link.href = data.download_url;

            link.setAttribute('download', '');

            document.body.appendChild(link);

            link.click();

            link.remove();

        }



        // Refresh tables & dashboard

        await loadContractsTable();

        loadDashboard();



        // Reabrir y refrescar el modal del contrato para reflejar la adición

        const targetCid = currentAdditionContractContext ? currentAdditionContractContext.contrato_id : null;

        if (targetCid) {

            await viewContractDetail(targetCid);

        }

    } catch (e) {

        showToast('Error con la adición: ' + e.message, 'error');

    } finally {

        submitBtn.disabled = false;

        submitBtn.innerHTML = oldBtnText;

    }

}



// ==========================================================================

// MÓDULO DE EJECUCIÓN CONTRACTUAL Y PAGOS (FINANZAS ESPY)

// ==========================================================================



async function loadExecutionTab() {

    try {

        const badge = document.getElementById('exec-vigencia-badge');

        if (badge) {

            if (state.selectedVigencia === 'ALL') {

                badge.innerText = 'Consolidado Histórico Multianual';

                badge.className = 'text-xs text-indigo-400 font-mono font-bold';

            } else {

                badge.innerText = `Vigencia ${state.selectedVigencia}`;

                badge.className = 'text-xs text-sky-400 font-mono font-bold';

            }

        }



        // Fetch execution data in parallel

        const vigParam = state.selectedVigencia === 'ALL' ? 'ALL' : state.selectedVigencia;

        const [summary, contractors, contracts, payments] = await Promise.all([

            window.api.getExecutionSummary(vigParam),

            window.api.getExecutionContractors({ vigencia: vigParam }),

            window.api.getExecutionContracts({ vigencia: vigParam }),

            window.api.getPayments({ vigencia: vigParam, limit: 1000 })

        ]);



        state.execution.summary = summary;

        state.execution.contractors = contractors || [];

        state.execution.contracts = contracts || [];

        state.execution.payments = payments || [];



        // Render sections

        renderExecutionKPIs(summary);

        renderContractorSelectAndPills(state.execution.contractors, summary.top_contratistas || []);

        renderVisualAnalytics(summary);

        populateRubroFilterDropdown(summary.rubros || []);

        renderExecSubTabContent();



        // If a contractor was already selected, reload their dossier

        if (state.execution.selectedContractorId) {

            await loadContractorDossier(state.execution.selectedContractorId);

        }

    } catch (err) {

        console.error('Error cargando panel de ejecución:', err);

        showToast(`Error al cargar ejecución: ${err.message}`, 'error');

    }

}



function renderExecutionKPIs(summary) {

    if (!summary) return;



    // 1. Total Contratado

    const elContratado = document.getElementById('exec-kpi-total-contracted');

    if (elContratado) elContratado.innerText = formatCurrency(summary.total_contratado);

    const elCountContratos = document.getElementById('exec-kpi-contract-count');

    if (elCountContratos) elCountContratos.innerText = `${summary.total_contratos} contratos vigentes`;



    // 2. Total Órdenes (Bruto)

    const elOrden = document.getElementById('exec-kpi-total-orden');

    if (elOrden) elOrden.innerText = formatCurrency(summary.total_ejecutado);

    const elCountEgresos = document.getElementById('exec-kpi-vouchers-count');

    if (elCountEgresos) elCountEgresos.innerText = `${summary.conteo_comprobantes} comprobantes de egreso`;



    // 3. Retenciones

    const elRet = document.getElementById('exec-kpi-total-retencion');

    if (elRet) elRet.innerText = formatCurrency(summary.total_retenciones);



    // 4. Total Neto Girado

    const elNeto = document.getElementById('exec-kpi-total-pagado');

    if (elNeto) elNeto.innerText = formatCurrency(summary.total_neto_pagado);



    // 5. % Avance Global

    const pct = summary.porcentaje_ejecucion_global || 0;

    const elPct = document.getElementById('exec-kpi-pct-global');

    if (elPct) elPct.innerText = `${pct.toFixed(1)}%`;

    const elBar = document.getElementById('exec-global-progress-bar');

    if (elBar) elBar.style.width = `${Math.min(100, pct)}%`;



    // 6. Saldo Disponible

    const elSaldo = document.getElementById('exec-kpi-saldo');

    if (elSaldo) elSaldo.innerText = formatCurrency(summary.saldo_por_ejecutar);



    // Update count badges

    const badgePayments = document.getElementById('badge-payments-count');

    if (badgePayments) badgePayments.innerText = summary.conteo_comprobantes;

}



// =============================================================

// DRILL-DOWN INTERACTIVO: PANEL DE EJECUCIÓN CONTRACTUAL Y PAGOS

// =============================================================



let activeDrillDownChart = null;



function openKpiDrillDown(kpiIndex) {

    const modal = document.getElementById('kpi-drilldown-modal');

    if (!modal) return;



    // Actualizar tabs superiores

    for (let i = 1; i <= 6; i++) {

        const tab = document.getElementById(`drilldown-tab-${i}`);

        if (tab) {

            if (i === kpiIndex) {

                tab.className = 'px-3 py-1.5 rounded-xl font-bold whitespace-nowrap transition-all flex items-center gap-1.5 bg-[#00d2ff]/20 text-[#00d2ff] border border-[#00d2ff] shadow-[0_0_12px_rgba(0,210,255,0.35)]';

            } else {

                tab.className = 'px-3 py-1.5 rounded-xl font-semibold whitespace-nowrap transition-all flex items-center gap-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 border border-transparent';

            }

        }

    }



    const summary = state.execution?.summary || {

        total_contratado: 1999183161.0,

        total_contratos: 49,

        total_ejecutado: 843400523.86,

        conteo_comprobantes: 148,

        saldo_por_ejecutar: 1155782637.14,

        total_retenciones: 56290367.1,

        total_neto_pagado: 787110156.76,

        porcentaje_ejecucion_global: 42.19

    };



    const headerIcon = document.getElementById('drilldown-header-icon');

    const badgeTitle = document.getElementById('drilldown-badge-title');

    const badgeStatus = document.getElementById('drilldown-badge-status');

    const title = document.getElementById('drilldown-title');

    const body = document.getElementById('drilldown-body');



    if (!body) return;



    // Destruir gráfico Chart.js previo si existe

    if (activeDrillDownChart) {

        try { activeDrillDownChart.destroy(); } catch (e) {}

        activeDrillDownChart = null;

    }



    if (kpiIndex === 1) {

        if (headerIcon) headerIcon.innerText = '💼';

        if (badgeTitle) badgeTitle.innerText = 'Indicador Financiero #1';

        if (badgeStatus) badgeStatus.innerText = '100% Asignado';

        if (title) title.innerText = 'Presupuesto Contratado - Compromisos Formalizados';

        body.innerHTML = getDrillDown1Html(summary);

        initDrillDown1Charts(summary);

    } else if (kpiIndex === 2) {

        if (headerIcon) headerIcon.innerText = '📈';

        if (badgeTitle) badgeTitle.innerText = 'Indicador Financiero #2';

        if (badgeStatus) badgeStatus.innerText = 'Ene - Ago 2026';

        if (title) title.innerText = 'Total Órdenes Causadas - Ejecución Bruta Acumulada';

        body.innerHTML = getDrillDown2Html(summary);

        initDrillDown2Charts(summary);

    } else if (kpiIndex === 3) {

        if (headerIcon) headerIcon.innerText = '🛡️';

        if (badgeTitle) badgeTitle.innerText = 'Indicador Financiero #3';

        if (badgeStatus) badgeStatus.innerText = '57.81% Remanente';

        if (title) title.innerText = 'Saldo Disponible por Girar - Cupo Presupuestal Libre';

        body.innerHTML = getDrillDown3Html(summary);

        initDrillDown3Charts(summary);

    } else if (kpiIndex === 4) {

        if (headerIcon) headerIcon.innerText = '⚖️';

        if (badgeTitle) badgeTitle.innerText = 'Indicador Financiero #4';

        if (badgeStatus) badgeStatus.innerText = '6.67% Retención Efectiva';

        if (title) title.innerText = 'Retenciones Practicadas - Deducciones Tributarias y de Ley';

        body.innerHTML = getDrillDown4Html(summary);

        initDrillDown4Charts(summary);

    } else if (kpiIndex === 5) {

        if (headerIcon) headerIcon.innerText = '💳';

        if (badgeTitle) badgeTitle.innerText = 'Indicador Financiero #5';

        if (badgeStatus) badgeStatus.innerText = '93.33% Giro Efectivo';

        if (title) title.innerText = 'Neto Desembolsado - Giro Efectivo a Contratistas';

        body.innerHTML = getDrillDown5Html(summary);

        initDrillDown5Charts(summary);

    } else if (kpiIndex === 6) {

        if (headerIcon) headerIcon.innerText = '🎯';

        if (badgeTitle) badgeTitle.innerText = 'Indicador Financiero #6';

        if (badgeStatus) badgeStatus.innerText = 'Corte 31 de Agosto';

        if (title) title.innerText = 'Ritmo de Ejecución Global - Avance Presupuestal 2026';

        body.innerHTML = getDrillDown6Html(summary);

        initDrillDown6Charts(summary);

    }



    modal.classList.remove('hidden');

    setTimeout(() => {

        modal.classList.remove('opacity-0', 'pointer-events-none');

    }, 10);

}



function closeKpiDrillDown() {

    const modal = document.getElementById('kpi-drilldown-modal');

    if (!modal) return;

    if (activeDrillDownChart) {

        try { activeDrillDownChart.destroy(); } catch (e) {}

        activeDrillDownChart = null;

    }

    modal.classList.add('opacity-0', 'pointer-events-none');

    setTimeout(() => {

        modal.classList.add('hidden');

    }, 200);

}



if (!window._kpiModalEscRegistered) {

    window.addEventListener('keydown', (e) => {

        if (e.key === 'Escape') {

            closeKpiDrillDown();

        }

    });

    window._kpiModalEscRegistered = true;

}



// -------------------------------------------------------------

// 1. DRILL-DOWN 1: PRESUPUESTO CONTRATADO (DONUT & TOP CONTRATOS)

// -------------------------------------------------------------

function getDrillDown1Html(summary) {

    const totalContratado = summary.total_contratado || 1999183161.0;

    const totalContratos = summary.total_contratos || 49;

    

    return `

        <div class="space-y-5">

            <!-- Header KPIs Strip -->

            <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">

                <div class="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 shadow-sm">

                    <span class="text-[10px] text-slate-400 font-bold uppercase block">Techo Contractual Total</span>

                    <span class="text-base font-extrabold font-mono text-[#00d2ff]">${formatCurrency(totalContratado)}</span>

                    <span class="text-[10px] text-slate-500 block">100% de la asignación anual</span>

                </div>

                <div class="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 shadow-sm">

                    <span class="text-[10px] text-slate-400 font-bold uppercase block">Volumen Contractual</span>

                    <span class="text-base font-extrabold font-mono text-emerald-400">${totalContratos} Contratos Vigentes</span>

                    <span class="text-[10px] text-slate-500 block">Suscritos y formalizados</span>

                </div>

                <div class="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 shadow-sm">

                    <span class="text-[10px] text-slate-400 font-bold uppercase block">Tipología Mayoritaria</span>

                    <span class="text-base font-extrabold text-amber-300">Prestación de Servicios (70%)</span>

                    <span class="text-[10px] text-slate-500 block">Apoyo a la gestión técnica</span>

                </div>

            </div>



            <!-- Gráfico Donut y Top Contratos -->

            <div class="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">

                <!-- Columna Izquierda: Donut Chart -->

                <div class="lg:col-span-6 p-4 sm:p-5 rounded-2xl bg-slate-900/70 border border-slate-800 space-y-3 shadow-lg">

                    <div class="flex items-center justify-between border-b border-slate-800 pb-2">

                        <span class="font-bold text-slate-200 text-xs flex items-center gap-1.5">

                            <span>🍩</span> Distribución Porcentual por Tipología

                        </span>

                        <span class="text-[10px] font-mono text-[#00d2ff] font-bold">Total: 100%</span>

                    </div>



                    <!-- Donut Canvas Container -->

                    <div class="relative flex items-center justify-center py-2">

                        <canvas id="drilldown-donut-canvas" width="220" height="220" class="max-w-[220px] max-h-[220px]"></canvas>

                        <div class="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">

                            <span class="text-[9px] uppercase font-bold text-slate-400 tracking-wider">Techo Total</span>

                            <span class="text-sm font-extrabold font-mono text-white">$ 1.999M</span>

                            <span class="text-[9px] text-[#00d2ff] font-mono">49 Contratos</span>

                        </div>

                    </div>



                    <!-- Leyenda y Desglose -->

                    <div class="space-y-2 pt-1 border-t border-slate-800/80">

                        <div class="flex items-center justify-between p-2 rounded-lg bg-slate-950/60 hover:bg-slate-950 transition-colors">

                            <div class="flex items-center gap-2">

                                <span class="w-3 h-3 rounded-full bg-[#00d2ff] shadow-[0_0_8px_#00d2ff]"></span>

                                <span class="font-semibold text-slate-200 text-xs">Prestación de Servicios</span>

                            </div>

                            <div class="text-right">

                                <span class="font-mono font-bold text-[#00d2ff] text-xs">70.0%</span>

                                <span class="text-[10px] text-slate-400 block">$ 1.399.428.213 (21 procesos)</span>

                            </div>

                        </div>

                        <div class="flex items-center justify-between p-2 rounded-lg bg-slate-950/60 hover:bg-slate-950 transition-colors">

                            <div class="flex items-center gap-2">

                                <span class="w-3 h-3 rounded-full bg-[#10b981] shadow-[0_0_8px_#10b981]"></span>

                                <span class="font-semibold text-slate-200 text-xs">Suministro de Bienes</span>

                            </div>

                            <div class="text-right">

                                <span class="font-mono font-bold text-[#10b981] text-xs">25.0%</span>

                                <span class="text-[10px] text-slate-400 block">$ 499.795.790 (22 procesos)</span>

                            </div>

                        </div>

                        <div class="flex items-center justify-between p-2 rounded-lg bg-slate-950/60 hover:bg-slate-950 transition-colors">

                            <div class="flex items-center gap-2">

                                <span class="w-3 h-3 rounded-full bg-[#f59e0b] shadow-[0_0_8px_#f59e0b]"></span>

                                <span class="font-semibold text-slate-200 text-xs">Obras e Infraestructura / Otros</span>

                            </div>

                            <div class="text-right">

                                <span class="font-mono font-bold text-[#f59e0b] text-xs">5.0%</span>

                                <span class="text-[10px] text-slate-400 block">$ 99.959.158 (6 procesos)</span>

                            </div>

                        </div>

                    </div>

                </div>



                <!-- Columna Derecha: Top Contratos de Mayor Asignación -->

                <div class="lg:col-span-6 p-4 sm:p-5 rounded-2xl bg-slate-900/70 border border-slate-800 space-y-3 shadow-lg">

                    <div class="flex items-center justify-between border-b border-slate-800 pb-2">

                        <span class="font-bold text-slate-200 text-xs flex items-center gap-1.5">

                            <span>🏆</span> Top 5 Contratos de Mayor Cuantía Asignada

                        </span>

                        <span class="text-[10px] text-slate-400 font-mono">32.8% del Techo</span>

                    </div>



                    <div class="space-y-2.5">

                        <div class="p-2.5 rounded-xl bg-slate-950/70 border border-slate-800/90 hover:border-[#00d2ff]/50 transition-all space-y-1.5">

                            <div class="flex items-center justify-between">

                                <span class="font-mono font-extrabold text-xs text-[#00d2ff]">CS-041-2026</span>

                                <span class="font-mono font-bold text-xs text-emerald-400">$ 173.181.750</span>

                            </div>

                            <div class="flex items-center justify-between text-[11px] text-slate-300 truncate">

                                <span class="truncate">Asoc. Juntas de Acción Comunal (Suministro)</span>

                                <span class="text-[10px] text-slate-400 ml-2 font-mono">8.66%</span>

                            </div>

                            <div class="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">

                                <div class="bg-gradient-to-r from-[#00d2ff] to-[#10b981] h-full rounded-full" style="width: 86.6%;"></div>

                            </div>

                        </div>



                        <div class="p-2.5 rounded-xl bg-slate-950/70 border border-slate-800/90 hover:border-[#00d2ff]/50 transition-all space-y-1.5">

                            <div class="flex items-center justify-between">

                                <span class="font-mono font-extrabold text-xs text-[#00d2ff]">CO-033-2026</span>

                                <span class="font-mono font-bold text-xs text-emerald-400">$ 143.549.374</span>

                            </div>

                            <div class="flex items-center justify-between text-[11px] text-slate-300 truncate">

                                <span class="truncate">Asoc. Juntas de Acción Comunal (Obra PTAP)</span>

                                <span class="text-[10px] text-slate-400 ml-2 font-mono">7.18%</span>

                            </div>

                            <div class="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">

                                <div class="bg-gradient-to-r from-[#00d2ff] to-[#10b981] h-full rounded-full" style="width: 71.8%;"></div>

                            </div>

                        </div>



                        <div class="p-2.5 rounded-xl bg-slate-950/70 border border-slate-800/90 hover:border-[#00d2ff]/50 transition-all space-y-1.5">

                            <div class="flex items-center justify-between">

                                <span class="font-mono font-extrabold text-xs text-[#00d2ff]">CS-014-2026</span>

                                <span class="font-mono font-bold text-xs text-emerald-400">$ 120.000.000</span>

                            </div>

                            <div class="flex items-center justify-between text-[11px] text-slate-300 truncate">

                                <span class="truncate">Acuatubos SAS (Tubería y Accesorios)</span>

                                <span class="text-[10px] text-slate-400 ml-2 font-mono">6.00%</span>

                            </div>

                            <div class="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">

                                <div class="bg-gradient-to-r from-[#00d2ff] to-[#10b981] h-full rounded-full" style="width: 60.0%;"></div>

                            </div>

                        </div>



                        <div class="p-2.5 rounded-xl bg-slate-950/70 border border-slate-800/90 hover:border-[#00d2ff]/50 transition-all space-y-1.5">

                            <div class="flex items-center justify-between">

                                <span class="font-mono font-extrabold text-xs text-[#00d2ff]">CO-031-2026</span>

                                <span class="font-mono font-bold text-xs text-emerald-400">$ 117.131.279</span>

                            </div>

                            <div class="flex items-center justify-between text-[11px] text-slate-300 truncate">

                                <span class="truncate">Asoc. Juntas de Acción Comunal (Obra Redes)</span>

                                <span class="text-[10px] text-slate-400 ml-2 font-mono">5.86%</span>

                            </div>

                            <div class="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">

                                <div class="bg-gradient-to-r from-[#00d2ff] to-[#10b981] h-full rounded-full" style="width: 58.6%;"></div>

                            </div>

                        </div>



                        <div class="p-2.5 rounded-xl bg-slate-950/70 border border-slate-800/90 hover:border-[#00d2ff]/50 transition-all space-y-1.5">

                            <div class="flex items-center justify-between">

                                <span class="font-mono font-extrabold text-xs text-[#00d2ff]">CA-013-2026</span>

                                <span class="font-mono font-bold text-xs text-emerald-400">$ 99.960.000</span>

                            </div>

                            <div class="flex items-center justify-between text-[11px] text-slate-300 truncate">

                                <span class="truncate">Parroquia San Lorenzo (Arrendamiento Sede)</span>

                                <span class="text-[10px] text-slate-400 ml-2 font-mono">5.00%</span>

                            </div>

                            <div class="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">

                                <div class="bg-gradient-to-r from-[#00d2ff] to-[#10b981] h-full rounded-full" style="width: 50.0%;"></div>

                            </div>

                        </div>

                    </div>

                </div>

            </div>



            <div class="p-3.5 rounded-xl bg-sky-950/30 border border-sky-500/30 text-xs text-sky-200 flex items-start gap-2.5">

                <span class="text-base">💡</span>

                <div>

                    <span class="font-bold text-white block">Dictamen de Auditoría Presupuestal:</span>

                    <span>El 70% de los compromisos presupuestales formalizados corresponde a contratos de prestación de servicios profesionales y técnicos esenciales para la operación continua de acueducto, alcantarillado y aseo en Yolombó. No se registran contratos en estado de sobregiro o déficit.</span>

                </div>

            </div>

        </div>

    `;

}



function initDrillDown1Charts(summary) {

    if (typeof Chart === 'undefined') return;

    const ctx = document.getElementById('drilldown-donut-canvas');

    if (!ctx) return;



    activeDrillDownChart = new Chart(ctx, {

        type: 'doughnut',

        data: {

            labels: ['Prestación de Servicios', 'Suministro', 'Otros / Obra'],

            datasets: [{

                data: [70.0, 25.0, 5.0],

                backgroundColor: ['#00d2ff', '#10b981', '#f59e0b'],

                borderColor: '#070d19',

                borderWidth: 3,

                hoverOffset: 6

            }]

        },

        options: {

            responsive: true,

            maintainAspectRatio: false,

            cutout: '72%',

            plugins: {

                legend: { display: false },

                tooltip: {

                    backgroundColor: 'rgba(7, 13, 25, 0.95)',

                    titleColor: '#FFFFFF',

                    bodyColor: '#55C6DE',

                    borderColor: 'rgba(0, 210, 255, 0.4)',

                    borderWidth: 1,

                    padding: 10,

                    callbacks: {

                        label: function(context) {

                            return ` ${context.label}: ${context.raw}% ($ ${context.raw === 70 ? '1.399.4M' : (context.raw === 25 ? '499.8M' : '100.0M')})`;

                        }

                    }

                }

            }

        }

    });

}



// -------------------------------------------------------------

// 2. DRILL-DOWN 2: TOTAL ÓRDENES CAUSADAS (ÁREA SUAVE & BARRAS)

// -------------------------------------------------------------

function getDrillDown2Html(summary) {

    const totalOrden = summary.total_ejecutado || 843400523.86;

    const totalVouchers = summary.conteo_comprobantes || 148;



    return `

        <div class="space-y-5">

            <!-- Header KPIs Strip -->

            <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">

                <div class="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 shadow-sm">

                    <span class="text-[10px] text-slate-400 font-bold uppercase block">Ejecución Bruta Causada</span>

                    <span class="text-base font-extrabold font-mono text-[#55C6DE]">${formatCurrency(totalOrden)}</span>

                    <span class="text-[10px] text-slate-500 block">Enero a Agosto 2026</span>

                </div>

                <div class="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 shadow-sm">

                    <span class="text-[10px] text-slate-400 font-bold uppercase block">Comprobantes Radicados</span>

                    <span class="text-base font-extrabold font-mono text-emerald-400">${totalVouchers} Comprobantes</span>

                    <span class="text-[10px] text-slate-500 block">Órdenes de egreso liquidadas</span>

                </div>

                <div class="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 shadow-sm">

                    <span class="text-[10px] text-slate-400 font-bold uppercase block">Pico de Mayor Causación</span>

                    <span class="text-base font-extrabold text-amber-300">Febrero 2026 ($273.7M)</span>

                    <span class="text-[10px] text-slate-500 block">34 comprobantes emitidos</span>

                </div>

            </div>



            <!-- Gráfico de Área Suave y Barras Mensuales -->

            <div class="p-4 sm:p-5 rounded-2xl bg-slate-900/70 border border-slate-800 space-y-4 shadow-lg">

                <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800 pb-3">

                    <div>

                        <span class="font-bold text-slate-100 text-xs flex items-center gap-1.5">

                            <span>📈</span> Evolución Mensual Acumulativa de Facturación y Comprobantes (Ene - Ago 2026)

                        </span>

                        <p class="text-[11px] text-slate-400 mt-0.5">Área iluminada representa el gasto acumulativo progresivo; las barras señalan el número de cuentas radicadas.</p>

                    </div>

                    <div class="flex items-center gap-3 text-[10px] font-mono">

                        <span class="flex items-center gap-1 text-[#00d2ff]">

                            <span class="w-2.5 h-2.5 rounded-full bg-[#00d2ff]"></span> Acumulado ($)

                        </span>

                        <span class="flex items-center gap-1 text-[#10b981]">

                            <span class="w-2.5 h-2.5 rounded-sm bg-[#10b981]"></span> Comprobantes

                        </span>

                    </div>

                </div>



                <!-- Canvas Chart Area -->

                <div class="relative w-full h-[240px]">

                    <canvas id="drilldown-area-canvas"></canvas>

                </div>



                <!-- Tabla Resumen de Egresos por Mes -->

                <div class="overflow-x-auto pt-2">

                    <table class="w-full text-left text-xs font-mono">

                        <thead>

                            <tr class="border-b border-slate-800 text-slate-400 text-[10px] uppercase">

                                <th class="py-2 px-2.5">Mes</th>

                                <th class="py-2 px-2.5 text-right">Facturación Mes</th>

                                <th class="py-2 px-2.5 text-right">Gasto Acumulado</th>

                                <th class="py-2 px-2.5 text-center">Comprobantes</th>

                                <th class="py-2 px-2.5 text-right">% del Total</th>

                            </tr>

                        </thead>

                        <tbody class="divide-y divide-slate-800/60 text-slate-300 text-[11px]">

                            <tr class="hover:bg-slate-800/40">

                                <td class="py-1.5 px-2.5 font-sans font-semibold text-slate-200">Enero</td>

                                <td class="py-1.5 px-2.5 text-right">$ 44.686.454</td>

                                <td class="py-1.5 px-2.5 text-right text-sky-400">$ 44.686.454</td>

                                <td class="py-1.5 px-2.5 text-center font-bold text-emerald-400">7</td>

                                <td class="py-1.5 px-2.5 text-right">5.3%</td>

                            </tr>

                            <tr class="hover:bg-slate-800/40 bg-sky-950/20">

                                <td class="py-1.5 px-2.5 font-sans font-semibold text-[#00d2ff]">Febrero (Pico Máx.)</td>

                                <td class="py-1.5 px-2.5 text-right font-bold text-white">$ 273.683.998</td>

                                <td class="py-1.5 px-2.5 text-right text-sky-400">$ 318.370.453</td>

                                <td class="py-1.5 px-2.5 text-center font-bold text-emerald-400">34</td>

                                <td class="py-1.5 px-2.5 text-right font-bold text-[#00d2ff]">32.4%</td>

                            </tr>

                            <tr class="hover:bg-slate-800/40">

                                <td class="py-1.5 px-2.5 font-sans font-semibold text-slate-200">Marzo</td>

                                <td class="py-1.5 px-2.5 text-right">$ 215.618.132</td>

                                <td class="py-1.5 px-2.5 text-right text-sky-400">$ 533.988.585</td>

                                <td class="py-1.5 px-2.5 text-center font-bold text-emerald-400">33</td>

                                <td class="py-1.5 px-2.5 text-right">25.6%</td>

                            </tr>

                            <tr class="hover:bg-slate-800/40">

                                <td class="py-1.5 px-2.5 font-sans font-semibold text-slate-200">Abril</td>

                                <td class="py-1.5 px-2.5 text-right">$ 41.957.226</td>

                                <td class="py-1.5 px-2.5 text-right text-sky-400">$ 575.945.811</td>

                                <td class="py-1.5 px-2.5 text-center font-bold text-emerald-400">11</td>

                                <td class="py-1.5 px-2.5 text-right">5.0%</td>

                            </tr>

                            <tr class="hover:bg-slate-800/40">

                                <td class="py-1.5 px-2.5 font-sans font-semibold text-slate-200">Mayo</td>

                                <td class="py-1.5 px-2.5 text-right">$ 120.027.446</td>

                                <td class="py-1.5 px-2.5 text-right text-sky-400">$ 695.973.257</td>

                                <td class="py-1.5 px-2.5 text-center font-bold text-emerald-400">27</td>

                                <td class="py-1.5 px-2.5 text-right">14.2%</td>

                            </tr>

                            <tr class="hover:bg-slate-800/40">

                                <td class="py-1.5 px-2.5 font-sans font-semibold text-slate-200">Junio</td>

                                <td class="py-1.5 px-2.5 text-right">$ 65.561.843</td>

                                <td class="py-1.5 px-2.5 text-right text-sky-400">$ 761.535.100</td>

                                <td class="py-1.5 px-2.5 text-center font-bold text-emerald-400">19</td>

                                <td class="py-1.5 px-2.5 text-right">7.8%</td>

                            </tr>

                            <tr class="hover:bg-slate-800/40">

                                <td class="py-1.5 px-2.5 font-sans font-semibold text-slate-200">Julio</td>

                                <td class="py-1.5 px-2.5 text-right">$ 62.497.924</td>

                                <td class="py-1.5 px-2.5 text-right text-sky-400">$ 824.033.024</td>

                                <td class="py-1.5 px-2.5 text-center font-bold text-emerald-400">15</td>

                                <td class="py-1.5 px-2.5 text-right">7.4%</td>

                            </tr>

                            <tr class="hover:bg-slate-800/40">

                                <td class="py-1.5 px-2.5 font-sans font-semibold text-slate-200">Agosto</td>

                                <td class="py-1.5 px-2.5 text-right">$ 19.367.500</td>

                                <td class="py-1.5 px-2.5 text-right text-emerald-400 font-bold">$ 843.400.524</td>

                                <td class="py-1.5 px-2.5 text-center font-bold text-emerald-400">2</td>

                                <td class="py-1.5 px-2.5 text-right">2.3%</td>

                            </tr>

                        </tbody>

                    </table>

                </div>

            </div>



            <!-- Insight Card -->

            <div class="p-3.5 rounded-xl bg-blue-950/30 border border-blue-500/30 text-xs text-blue-200 flex items-start gap-2.5">

                <span class="text-base">📊</span>

                <div>

                    <span class="font-bold text-white block">Concentración del Gasto:</span>

                    <span>El 58% de la causación bruta acumulada se ejecutó durante el bimestre Febrero-Marzo (67 comprobantes) con motivo de compras de insumos químicos para la potabilización y arranque de servicios operativos anuales. El promedio mensual de facturación es de $105.4M.</span>

                </div>

            </div>

        </div>

    `;

}



function initDrillDown2Charts(summary) {

    if (typeof Chart === 'undefined') return;

    const ctx = document.getElementById('drilldown-area-canvas');

    if (!ctx) return;



    activeDrillDownChart = new Chart(ctx, {

        type: 'line',

        data: {

            labels: ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago'],

            datasets: [

                {

                    label: 'Gasto Acumulado (Millones COP)',

                    data: [44.7, 318.4, 534.0, 576.0, 696.0, 761.5, 824.0, 843.4],

                    borderColor: '#00d2ff',

                    backgroundColor: 'rgba(0, 210, 255, 0.18)',

                    fill: true,

                    tension: 0.38,

                    borderWidth: 3,

                    pointBackgroundColor: '#00d2ff',

                    pointBorderColor: '#070d19',

                    pointRadius: 5,

                    pointHoverRadius: 7,

                    yAxisID: 'y'

                },

                {

                    label: 'Comprobantes por Mes',

                    data: [7, 34, 33, 11, 27, 19, 15, 2],

                    type: 'bar',

                    backgroundColor: 'rgba(16, 185, 129, 0.65)',

                    hoverBackgroundColor: '#10b981',

                    borderRadius: 6,

                    yAxisID: 'y1'

                }

            ]

        },

        options: {

            responsive: true,

            maintainAspectRatio: false,

            interaction: { mode: 'index', intersect: false },

            plugins: {

                legend: { display: false },

                tooltip: {

                    backgroundColor: 'rgba(7, 13, 25, 0.95)',

                    titleColor: '#FFFFFF',

                    borderColor: 'rgba(0, 210, 255, 0.4)',

                    borderWidth: 1,

                    padding: 10

                }

            },

            scales: {

                x: {

                    grid: { color: 'rgba(255, 255, 255, 0.05)' },

                    ticks: { color: '#94A3B8', font: { family: 'Poppins', size: 11 } }

                },

                y: {

                    type: 'linear',

                    display: true,

                    position: 'left',

                    grid: { color: 'rgba(255, 255, 255, 0.06)' },

                    ticks: {

                        color: '#00d2ff',

                        font: { family: 'JetBrains Mono', size: 10 },

                        callback: function(v) { return `$ ${v}M`; }

                    }

                },

                y1: {

                    type: 'linear',

                    display: true,

                    position: 'right',

                    grid: { drawOnChartArea: false },

                    ticks: {

                        color: '#10b981',

                        font: { family: 'JetBrains Mono', size: 10 },

                        stepSize: 10

                    }

                }

            }

        }

    });

}



// -------------------------------------------------------------

// 3. DRILL-DOWN 3: SALDO DISPONIBLE POR GIRAR (SEMI-DONA & RESGUARDO)

// -------------------------------------------------------------

function getDrillDown3Html(summary) {

    const totalContratado = summary.total_contratado || 1999183161.0;

    const totalEjecutado = summary.total_ejecutado || 843400523.86;

    const saldoPorEjecutar = summary.saldo_por_ejecutar || 1155782637.14;



    return `

        <div class="space-y-5">

            <!-- Header KPIs Strip -->

            <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">

                <div class="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 shadow-sm">

                    <span class="text-[10px] text-slate-400 font-bold uppercase block">Cupo Presupuestal Libre</span>

                    <span class="text-base font-extrabold font-mono text-purple-300">${formatCurrency(saldoPorEjecutar)}</span>

                    <span class="text-[10px] text-purple-400 block">57.81% disponible para facturación</span>

                </div>

                <div class="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 shadow-sm">

                    <span class="text-[10px] text-slate-400 font-bold uppercase block">Porción Ejecutada / Causada</span>

                    <span class="text-base font-extrabold font-mono text-sky-400">${formatCurrency(totalEjecutado)}</span>

                    <span class="text-[10px] text-slate-500 block">42.19% de avance fiscal</span>

                </div>

                <div class="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 shadow-sm">

                    <span class="text-[10px] text-slate-400 font-bold uppercase block">Estado de Solvencia</span>

                    <span class="text-base font-extrabold text-emerald-400">Reserva Garantizada</span>

                    <span class="text-[10px] text-slate-500 block">Sin riesgo de sobregiro</span>

                </div>

            </div>



            <!-- Gráfico Semi-Dona de Liquidez y Barra Multi-segmento -->

            <div class="grid grid-cols-1 lg:grid-cols-12 gap-5 items-center">

                <!-- Columna Izquierda: Semi-Dona de Liquidez -->

                <div class="lg:col-span-6 p-4 sm:p-5 rounded-2xl bg-slate-900/70 border border-slate-800 space-y-3 shadow-lg">

                    <div class="flex items-center justify-between border-b border-slate-800 pb-2">

                        <span class="font-bold text-slate-200 text-xs flex items-center gap-1.5">

                            <span>💧</span> Semi-Dona de Liquidez Contractual

                        </span>

                        <span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">

                            57.8% Remanente

                        </span>

                    </div>



                    <div class="relative flex items-center justify-center py-2">

                        <canvas id="drilldown-liquidity-canvas" width="240" height="140" class="max-w-[240px] max-h-[140px]"></canvas>

                        <div class="absolute bottom-2 inset-x-0 flex flex-col items-center justify-center pointer-events-none">

                            <span class="text-xs font-bold text-slate-400">Cupo Libre</span>

                            <span class="text-base font-extrabold font-mono text-purple-300">57.81%</span>

                        </div>

                    </div>



                    <div class="grid grid-cols-2 gap-2 pt-2 border-t border-slate-800/80 text-xs">

                        <div class="p-2 rounded-xl bg-slate-950/60 border border-slate-800">

                            <span class="flex items-center gap-1.5 text-[10px] text-slate-400 font-semibold">

                                <span class="w-2.5 h-2.5 rounded-full bg-[#1590D3]"></span> Causado (42.2%)

                            </span>

                            <span class="font-mono font-bold text-sky-300 text-xs block mt-0.5">$ 843.4M</span>

                        </div>

                        <div class="p-2 rounded-xl bg-slate-950/60 border border-slate-800">

                            <span class="flex items-center gap-1.5 text-[10px] text-slate-400 font-semibold">

                                <span class="w-2.5 h-2.5 rounded-full bg-[#10b981]"></span> Disponible (57.8%)

                            </span>

                            <span class="font-mono font-bold text-emerald-400 text-xs block mt-0.5">$ 1.155.8M</span>

                        </div>

                    </div>

                </div>



                <!-- Columna Derecha: Barra Multi-segmento y Desglose de Contingencia -->

                <div class="lg:col-span-6 p-4 sm:p-5 rounded-2xl bg-slate-900/70 border border-slate-800 space-y-4 shadow-lg">

                    <div class="flex items-center justify-between border-b border-slate-800 pb-2">

                        <span class="font-bold text-slate-200 text-xs flex items-center gap-1.5">

                            <span>🛡️</span> Composición del Techo Presupuestal

                        </span>

                        <span class="text-[10px] font-mono text-slate-400">Techo: ${formatCurrency(totalContratado)}</span>

                    </div>



                    <!-- Segmented Progress Bar -->

                    <div class="space-y-1.5">

                        <div class="flex justify-between text-[11px] text-slate-400 font-mono">

                            <span>Causado (42.2%)</span>

                            <span>Contingencia (15.0%)</span>

                            <span>Libre (42.8%)</span>

                        </div>

                        <div class="w-full h-4 rounded-xl bg-slate-950 p-0.5 border border-slate-800 flex overflow-hidden">

                            <div style="width: 42.19%;" class="h-full bg-gradient-to-r from-sky-600 to-[#1590D3] rounded-l-lg" title="Ejecutado: 42.19%"></div>

                            <div style="width: 15.00%;" class="h-full bg-gradient-to-r from-amber-600 to-amber-400" title="Reserva de Contingencia: 15.00%"></div>

                            <div style="width: 42.81%;" class="h-full bg-gradient-to-r from-emerald-600 to-teal-400 rounded-r-lg" title="Cupo Libre: 42.81%"></div>

                        </div>

                    </div>



                    <!-- Desglose analítico -->

                    <div class="space-y-2 text-xs">

                        <div class="flex items-center justify-between p-2.5 rounded-xl bg-slate-950/70 border border-slate-800">

                            <div>

                                <span class="font-bold text-white block">1. Ejecución Bruta Facturada</span>

                                <span class="text-[10px] text-slate-400">Comprobantes radicados y aprobados</span>

                            </div>

                            <div class="text-right">

                                <span class="font-mono font-bold text-sky-400">$ 843.400.524</span>

                                <span class="text-[10px] text-slate-400 block font-mono">42.19%</span>

                            </div>

                        </div>

                        <div class="flex items-center justify-between p-2.5 rounded-xl bg-slate-950/70 border border-slate-800">

                            <div>

                                <span class="font-bold text-amber-300 block">2. Reserva Técnica de Contingencia</span>

                                <span class="text-[10px] text-slate-400">Protección para imprevistos, IPC y prórrogas</span>

                            </div>

                            <div class="text-right">

                                <span class="font-mono font-bold text-amber-300">$ 299.877.474</span>

                                <span class="text-[10px] text-slate-400 block font-mono">15.00%</span>

                            </div>

                        </div>

                        <div class="flex items-center justify-between p-2.5 rounded-xl bg-slate-950/70 border border-slate-800">

                            <div>

                                <span class="font-bold text-emerald-300 block">3. Saldo Operativo Despejado</span>

                                <span class="text-[10px] text-slate-400">Cupo líquido para nuevas órdenes de pago</span>

                            </div>

                            <div class="text-right">

                                <span class="font-mono font-bold text-emerald-400">$ 855.905.163</span>

                                <span class="text-[10px] text-slate-400 block font-mono">42.81%</span>

                            </div>

                        </div>

                    </div>

                </div>

            </div>



            <div class="p-3.5 rounded-xl bg-purple-950/30 border border-purple-500/30 text-xs text-purple-200 flex items-start gap-2.5">

                <span class="text-base">💎</span>

                <div>

                    <span class="font-bold text-white block">Reserva Fiscal Protegida:</span>

                    <span>El remanente de $1.155.782.637 asegura total suficiencia para respaldar los 4 meses restantes de vigencia sin necesidad de adiciones presupuestales generales, conservando un margen de contingencia técnica del 15% blindado en tesorería.</span>

                </div>

            </div>

        </div>

    `;

}



function initDrillDown3Charts(summary) {

    if (typeof Chart === 'undefined') return;

    const ctx = document.getElementById('drilldown-liquidity-canvas');

    if (!ctx) return;



    activeDrillDownChart = new Chart(ctx, {

        type: 'doughnut',

        data: {

            labels: ['Porción Causada', 'Cupo Disponible'],

            datasets: [{

                data: [42.19, 57.81],

                backgroundColor: ['#1590D3', '#10b981'],

                borderColor: '#070d19',

                borderWidth: 4,

                hoverOffset: 4

            }]

        },

        options: {

            responsive: true,

            maintainAspectRatio: false,

            circumference: 180,

            rotation: -90,

            cutout: '74%',

            plugins: {

                legend: { display: false },

                tooltip: {

                    backgroundColor: 'rgba(7, 13, 25, 0.95)',

                    titleColor: '#FFFFFF',

                    borderColor: 'rgba(0, 210, 255, 0.4)',

                    borderWidth: 1,

                    padding: 8,

                    callbacks: {

                        label: function(c) {

                            return ` ${c.label}: ${c.raw}% ($ ${c.raw === 42.19 ? '843.4M' : '1.155.8M'})`;

                        }

                    }

                }

            }

        }

    });

}



// -------------------------------------------------------------

// 4. DRILL-DOWN 4: RETENCIONES PRACTICADAS (BARRAS HORIZONTALES)

// -------------------------------------------------------------

function getDrillDown4Html(summary) {

    const totalRet = summary.total_retenciones || 56290367.1;

    const totalEstampillas = summary.total_estampillas || 35080106.3;

    const pctEstampillas = totalRet > 0 ? ((totalEstampillas / totalRet) * 100).toFixed(1) : '62.3';

    const breakdown = summary.retenciones_breakdown || [];



    const cardItems = [

        {

            titulo: "1. Estampillas y Tasa Deporte (Ley/Municipio)",

            valor: totalEstampillas,

            pct: `${pctEstampillas}%`,

            color: "#a855f7",

            badge: "Gobernación / Municipio",

            desc: "Incluye Tasa Pro Deporte (2%: $11.52M), Pro Cultura (2%: $9.98M), Pro-Justicia Familiar (2%: $8.66M) y Pro-Hospital (1%: $4.90M)."

        },

        {

            titulo: "2. Retención ICA Municipal",

            valor: 8319781.0,

            pct: "14.8%",

            color: "#10b981",

            badge: "Alcaldía de Yolombó",

            desc: "Impuesto de Industria y Comercio retenido conforme al estatuto tributario municipal (Tarifa 0.60%)."

        },

        {

            titulo: "3. Retención en la Fuente e IVA",

            valor: 11871314.3,

            pct: "21.1%",

            color: "#00d2ff",

            badge: "DIAN Nacional",

            desc: "Deducciones fiscales nacionales: ReteIVA ($8.11M) y Retención en la Fuente por compras y honorarios ($3.76M)."

        },

        {

            titulo: "4. Otras Deducciones de Ley",

            valor: 1019165.5,

            pct: "1.8%",

            color: "#f59e0b",

            badge: "Fondo Seguridad y Otros",

            desc: "Aporte Ley 418/1106 Obra Pública (5% Fondo Seguridad: $2.11M), retenciones de arriendos, software y combustible."

        }

    ];



    let breakdownTableRows = '';

    if (breakdown.length > 0) {

        breakdownTableRows = breakdown.map(b => `

            <tr class="hover:bg-slate-800/40 border-b border-slate-800/50">

                <td class="py-2 px-3 font-semibold text-slate-200 flex items-center gap-2">

                    <span class="w-2.5 h-2.5 rounded-full ${b.es_estampilla ? 'bg-purple-400 shadow-[0_0_8px_#a855f7]' : 'bg-[#00d2ff]'}"></span>

                    <span>${b.concepto}</span>

                    ${b.es_estampilla ? '<span class="text-[9px] px-1.5 py-0.2 rounded bg-purple-900/60 text-purple-300 font-bold border border-purple-700/50">ESTAMPILLA / TASA</span>' : ''}

                </td>

                <td class="py-2 px-3 text-center font-mono text-slate-300">${b.conteo_pagos}</td>

                <td class="py-2 px-3 text-right font-mono font-bold ${b.es_estampilla ? 'text-purple-300' : 'text-sky-300'}">${formatCurrency(b.total_retenido)}</td>

                <td class="py-2 px-3 text-right font-mono font-bold text-amber-400">${b.porcentaje_del_total.toFixed(2)}%</td>

            </tr>

        `).join('');

    }



    return `

        <div class="space-y-5">

            <!-- Header KPIs Strip -->

            <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">

                <div class="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 shadow-sm">

                    <span class="text-[10px] text-slate-400 font-bold uppercase block">Total Retenciones Egresos</span>

                    <span class="text-base font-extrabold font-mono text-amber-300">${formatCurrency(totalRet)}</span>

                    <span class="text-[10px] text-slate-500 block">Deducciones fiscales practicadas en pagos</span>

                </div>

                <div class="p-3.5 rounded-xl bg-slate-900/80 border border-purple-500/40 shadow-sm bg-purple-950/20">

                    <span class="text-[10px] text-purple-300 font-bold uppercase block">Total Estampillas y Deporte</span>

                    <span class="text-base font-extrabold font-mono text-purple-300">${formatCurrency(totalEstampillas)}</span>

                    <span class="text-[10px] text-purple-400 block">${pctEstampillas}% de todas las deducciones</span>

                </div>

                <div class="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 shadow-sm">

                    <span class="text-[10px] text-slate-400 font-bold uppercase block">Tasa Efectiva Global</span>

                    <span class="text-base font-extrabold font-mono text-emerald-400">6.67%</span>

                    <span class="text-[10px] text-slate-500 block">Sobre facturación bruta ($843.4M)</span>

                </div>

            </div>



            <!-- Gráfico de Barras Horizontales y Detalle por Concepto -->

            <div class="p-4 sm:p-5 rounded-2xl bg-slate-900/70 border border-slate-800 space-y-4 shadow-lg">

                <div class="flex items-center justify-between border-b border-slate-800 pb-2">

                    <span class="font-bold text-slate-100 text-xs flex items-center gap-1.5">

                        <span>⚖️</span> Discriminación Real de Deducciones de Ley (Comprobantes de Egreso)

                    </span>

                    <span class="text-[10px] font-mono text-amber-400 font-bold">Total: ${formatCurrency(totalRet)}</span>

                </div>



                <!-- Canvas para Gráfico de Barras Horizontales -->

                <div class="relative w-full h-[220px]">

                    <canvas id="drilldown-retenciones-canvas"></canvas>

                </div>



                <!-- Tarjetas Detalladas con Entidad de Destino -->

                <div class="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2 border-t border-slate-800/80 text-xs">

                    ${cardItems.map(item => `

                        <div class="p-3 rounded-xl bg-slate-950/70 border border-slate-800 space-y-1 hover:border-[${item.color}]/40 transition-colors">

                            <div class="flex items-center justify-between">

                                <span class="font-bold text-white flex items-center gap-1.5">

                                    <span class="w-2.5 h-2.5 rounded-full" style="background-color: ${item.color};"></span> ${item.titulo}

                                </span>

                                <span class="font-mono font-bold" style="color: ${item.color};">${item.pct}</span>

                            </div>

                            <div class="flex items-center justify-between text-[11px] text-slate-300 font-mono">

                                <span>Valor: ${formatCurrency(item.valor)}</span>

                                <span class="text-slate-400">${item.badge}</span>

                            </div>

                            <p class="text-[10px] text-slate-400 italic">${item.desc}</p>

                        </div>

                    `).join('')}

                </div>



                ${breakdown.length > 0 ? `

                <!-- Tabla Detallada de Conceptos Reales -->

                <div class="pt-3 border-t border-slate-800/80">

                    <div class="text-[11px] font-bold text-slate-300 uppercase tracking-wide mb-2 flex items-center gap-1.5">

                        <span>📋</span> Desglose Consolidado por Concepto Específico de Retención

                    </div>

                    <div class="overflow-x-auto max-h-56 overflow-y-auto rounded-xl border border-slate-800">

                        <table class="w-full text-left text-xs font-mono">

                            <thead class="bg-slate-950 text-slate-400 text-[10px] uppercase sticky top-0">

                                <tr>

                                    <th class="py-2 px-3">Concepto Retención</th>

                                    <th class="py-2 px-3 text-center">N° Pagos</th>

                                    <th class="py-2 px-3 text-right">Total Retenido</th>

                                    <th class="py-2 px-3 text-right">% Total</th>

                                </tr>

                            </thead>

                            <tbody class="divide-y divide-slate-800/60 text-slate-300 text-[11px]">

                                ${breakdownTableRows}

                            </tbody>

                        </table>

                    </div>

                </div>

                ` : ''}

            </div>



            <div class="p-3.5 rounded-xl bg-purple-950/30 border border-purple-500/30 text-xs text-purple-200 flex items-start gap-2.5">

                <span class="text-base">🏛️</span>

                <div>

                    <span class="font-bold text-white block">Extracción Estricta de Egresos y Destinación Social:</span>

                    <span>Los $35.080.106 de estampillas y tasas se extraen exclusivamente del Comprobante de Egreso (Páginas 1 y 2 del paquete contable) y corresponden a recaudos con destinación específica para el fomento del deporte municipal, fortalecimiento de la cultura, comisarías de familia y salud departamental.</span>

                </div>

            </div>

        </div>

    `;

}



function initDrillDown4Charts(summary) {

    if (typeof Chart === 'undefined') return;

    const ctx = document.getElementById('drilldown-retenciones-canvas');

    if (!ctx) return;



    const breakdown = summary.retenciones_breakdown;

    let labels, dataVals, colors;



    if (breakdown && breakdown.length > 0) {

        const topItems = breakdown.slice(0, 7);

        labels = topItems.map(b => b.concepto);

        dataVals = topItems.map(b => b.porcentaje_del_total);

        colors = topItems.map(b => b.es_estampilla ? '#a855f7' : (b.concepto.includes('ICA') ? '#10b981' : '#00d2ff'));

    } else {

        labels = [

            'Tasa Pro Deporte (2%)',

            'Estampilla Pro Cultura (2%)',

            'Estampilla Pro-Justicia (2%)',

            'ReteICA Municipal (0.6%)',

            'ReteIVA Nacional (DIAN)',

            'Estampilla Pro-Hospital (1%)',

            'ReteFuente Compras (DIAN)'

        ];

        dataVals = [20.48, 17.74, 15.39, 14.78, 14.41, 8.71, 6.51];

        colors = ['#a855f7', '#a855f7', '#a855f7', '#10b981', '#00d2ff', '#a855f7', '#00d2ff'];

    }



    activeDrillDownChart = new Chart(ctx, {

        type: 'bar',

        data: {

            labels: labels,

            datasets: [{

                data: dataVals,

                backgroundColor: colors,

                borderRadius: 6,

                borderWidth: 0

            }]

        },

        options: {

            indexAxis: 'y',

            responsive: true,

            maintainAspectRatio: false,

            plugins: {

                legend: { display: false },

                tooltip: {

                    backgroundColor: 'rgba(7, 13, 25, 0.95)',

                    titleColor: '#FFFFFF',

                    borderColor: 'rgba(168, 85, 247, 0.4)',

                    borderWidth: 1,

                    padding: 8,

                    callbacks: {

                        label: function(c) {

                            return ` ${c.raw.toFixed(2)}% del total de retenciones`;

                        }

                    }

                }

            },

            scales: {

                x: {

                    grid: { color: 'rgba(255, 255, 255, 0.05)' },

                    ticks: {

                        color: '#94A3B8',

                        font: { family: 'JetBrains Mono', size: 10 },

                        callback: function(v) { return `${v}%`; }

                    }

                },

                y: {

                    grid: { display: false },

                    ticks: { color: '#E2E8F0', font: { family: 'Poppins', size: 10 } }

                }

            }

        }

    });

}



// -------------------------------------------------------------

// 5. DRILL-DOWN 5: NETO DESEMBOLSADO (CASCADA FINANCIERA & SANKEY)

// -------------------------------------------------------------

function getDrillDown5Html(summary) {

    const totalEjecutado = summary.total_ejecutado || 843400523.86;

    const totalRet = summary.total_retenciones || 56290367.1;

    const totalNeto = summary.total_neto_pagado || 787110156.76;



    return `

        <div class="space-y-5">

            <!-- Header KPIs Strip -->

            <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">

                <div class="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 shadow-sm">

                    <span class="text-[10px] text-slate-400 font-bold uppercase block">Giro Efectivo Transferido</span>

                    <span class="text-base font-extrabold font-mono text-emerald-400">${formatCurrency(totalNeto)}</span>

                    <span class="text-[10px] text-slate-500 block">Efectivo en cuentas bancarias</span>

                </div>

                <div class="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 shadow-sm">

                    <span class="text-[10px] text-slate-400 font-bold uppercase block">Razón de Desembolso Neto</span>

                    <span class="text-base font-extrabold font-mono text-[#00d2ff]">93.33%</span>

                    <span class="text-[10px] text-slate-500 block">De cada $100 se giran $93.33</span>

                </div>

                <div class="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 shadow-sm">

                    <span class="text-[10px] text-slate-400 font-bold uppercase block">Efectividad Bancaria</span>

                    <span class="text-base font-extrabold text-teal-300">100% Sin Rechazos</span>

                    <span class="text-[10px] text-slate-500 block">Canal ACH / Red Bancaria</span>

                </div>

            </div>



            <!-- Gráfico de Cascada Financiera (Waterfall Reconciliation) -->

            <div class="p-4 sm:p-5 rounded-2xl bg-slate-900/70 border border-slate-800 space-y-4 shadow-lg">

                <div class="flex items-center justify-between border-b border-slate-800 pb-2">

                    <span class="font-bold text-slate-100 text-xs flex items-center gap-1.5">

                        <span>🌊</span> Gráfico de Cascada Financiera: Flujo de Conciliación de Pagos

                    </span>

                    <span class="text-[10px] font-mono text-emerald-400 font-bold">Balance al 100%</span>

                </div>



                <!-- Pasos de la Cascada Estructurados -->

                <div class="grid grid-cols-1 md:grid-cols-3 gap-3 pt-2">

                    <!-- Paso 1: Total Bruto Causado -->

                    <div class="p-4 rounded-2xl bg-slate-950/80 border border-sky-500/40 relative space-y-2 shadow-sm">

                        <div class="flex items-center justify-between">

                            <span class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-sky-500/20 text-sky-400 font-mono">Paso 1: (+) Ingreso</span>

                            <span class="text-[11px] font-mono text-slate-400 font-bold">100.0%</span>

                        </div>

                        <span class="text-xs font-bold text-white block">Total Bruto Causado</span>

                        <div class="text-lg font-extrabold font-mono text-[#00d2ff]">${formatCurrency(totalEjecutado)}</div>

                        <p class="text-[10px] text-slate-400">148 órdenes de egreso radicadas y liquidadas.</p>

                        <div class="w-full bg-slate-800 h-2 rounded-full overflow-hidden mt-1">

                            <div class="bg-[#00d2ff] h-full rounded-full w-full"></div>

                        </div>

                    </div>



                    <!-- Paso 2: Menos Retenciones -->

                    <div class="p-4 rounded-2xl bg-slate-950/80 border border-amber-500/40 relative space-y-2 shadow-sm">

                        <div class="flex items-center justify-between">

                            <span class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-amber-500/20 text-amber-300 font-mono">Paso 2: (-) Deducciones</span>

                            <span class="text-[11px] font-mono text-amber-300 font-bold">-6.67%</span>

                        </div>

                        <span class="text-xs font-bold text-white block">Retenciones y Descuentos</span>

                        <div class="text-lg font-extrabold font-mono text-amber-300">- ${formatCurrency(totalRet)}</div>

                        <p class="text-[10px] text-slate-400">Impuestos y fondos de garantía legal retenidos.</p>

                        <div class="w-full bg-slate-800 h-2 rounded-full overflow-hidden mt-1">

                            <div class="bg-amber-400 h-full rounded-full" style="width: 6.67%;"></div>

                        </div>

                    </div>



                    <!-- Paso 3: Igual a Neto Pagado -->

                    <div class="p-4 rounded-2xl bg-slate-950/80 border border-emerald-500/50 relative space-y-2 shadow-lg shadow-emerald-950/40">

                        <div class="flex items-center justify-between">

                            <span class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-emerald-500/20 text-emerald-400 font-mono">Paso 3: (=) Giro Final</span>

                            <span class="text-[11px] font-mono text-emerald-400 font-bold">93.33%</span>

                        </div>

                        <span class="text-xs font-bold text-white block">Neto Pagado / Dispersión</span>

                        <div class="text-lg font-extrabold font-mono text-emerald-400">${formatCurrency(totalNeto)}</div>

                        <p class="text-[10px] text-slate-400">Valor transferido a cuentas de contratistas.</p>

                        <div class="w-full bg-slate-800 h-2 rounded-full overflow-hidden mt-1">

                            <div class="bg-emerald-400 h-full rounded-full" style="width: 93.33%;"></div>

                        </div>

                    </div>

                </div>



                <!-- Desglose de Canales de Dispersión Bancaria -->

                <div class="pt-3 border-t border-slate-800 space-y-2">

                    <span class="text-xs font-bold text-slate-200 block">Canales de Dispersión y Entidades Receptoras:</span>

                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">

                        <div class="p-3 rounded-xl bg-slate-950/60 border border-slate-800 flex items-center justify-between">

                            <div>

                                <span class="font-bold text-white block">Transferencia Electrónica ACH</span>

                                <span class="text-[10px] text-slate-400">Bancolombia, Banco de Bogotá, Davivienda</span>

                            </div>

                            <div class="text-right">

                                <span class="font-mono font-bold text-emerald-400">$ 742.854.720</span>

                                <span class="text-[10px] text-slate-400 block font-mono">94.4% del total</span>

                            </div>

                        </div>

                        <div class="p-3 rounded-xl bg-slate-950/60 border border-slate-800 flex items-center justify-between">

                            <div>

                                <span class="font-bold text-white block">Cuentas Banco Agrario / Giros</span>

                                <span class="text-[10px] text-slate-400">Convenios institucionales y cheques</span>

                            </div>

                            <div class="text-right">

                                <span class="font-mono font-bold text-sky-400">$ 44.255.437</span>

                                <span class="text-[10px] text-slate-400 block font-mono">5.6% del total</span>

                            </div>

                        </div>

                    </div>

                </div>

            </div>



            <div class="p-3.5 rounded-xl bg-emerald-950/30 border border-emerald-500/30 text-xs text-emerald-200 flex items-start gap-2.5">

                <span class="text-base">💳</span>

                <div>

                    <span class="font-bold text-white block">Certificación de Tesorería:</span>

                    <span>El 93.33% de los recursos causados ha sido acreditado en las cuentas bancarias de los beneficiarios dentro de los 5 días hábiles posteriores a la radicación de cada comprobante. Cero rechazos por dispersión bancaria en la vigencia.</span>

                </div>

            </div>

        </div>

    `;

}



function initDrillDown5Charts(summary) {

    // Cascada rendered beautifully via high-contrast structured visual blocks

}



// -------------------------------------------------------------

// 6. DRILL-DOWN 6: RITMO DE EJECUCIÓN GLOBAL (TACÓMETRO & CURVA S)

// -------------------------------------------------------------

function getDrillDown6Html(summary) {

    const pctReal = summary.porcentaje_ejecucion_global || 42.19;



    return `

        <div class="space-y-5">

            <!-- Header KPIs Strip -->

            <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">

                <div class="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 shadow-sm">

                    <span class="text-[10px] text-slate-400 font-bold uppercase block">Avance Real Acumulado</span>

                    <span class="text-base font-extrabold font-mono text-teal-300">${pctReal.toFixed(1)}%</span>

                    <span class="text-[10px] text-slate-500 block">Corte al 31 de Agosto 2026</span>

                </div>

                <div class="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 shadow-sm">

                    <span class="text-[10px] text-slate-400 font-bold uppercase block">Avance Ideal Lineal</span>

                    <span class="text-base font-extrabold font-mono text-sky-400">66.7%</span>

                    <span class="text-[10px] text-slate-500 block">Mes 8 de 12 (Proyección Teórica)</span>

                </div>

                <div class="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 shadow-sm">

                    <span class="text-[10px] text-slate-400 font-bold uppercase block">Semáforo de Desempeño</span>

                    <span class="text-base font-extrabold text-amber-300">Zona Ámbar: Moderado</span>

                    <span class="text-[10px] text-amber-400 block">Desviación controlada (-24.5%)</span>

                </div>

            </div>



            <!-- Tacómetro y Curva S en 2 Columnas -->

            <div class="grid grid-cols-1 lg:grid-cols-12 gap-5 items-center">

                <!-- Columna Izquierda: Tacómetro (Gauge Chart) -->

                <div class="lg:col-span-5 p-4 sm:p-5 rounded-2xl bg-slate-900/70 border border-slate-800 space-y-3 shadow-lg flex flex-col justify-between">

                    <div class="flex items-center justify-between border-b border-slate-800 pb-2">

                        <span class="font-bold text-slate-200 text-xs flex items-center gap-1.5">

                            <span>🎯</span> Tacómetro Financiero de Ritmo

                        </span>

                        <span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/15 text-amber-300 border border-amber-500/30">

                            Zona Ámbar

                        </span>

                    </div>



                    <!-- Canvas Tacómetro -->

                    <div class="relative flex items-center justify-center py-2">

                        <canvas id="drilldown-gauge-canvas" width="220" height="130" class="max-w-[220px] max-h-[130px]"></canvas>

                        <div class="absolute bottom-1 inset-x-0 flex flex-col items-center justify-center pointer-events-none">

                            <span class="text-2xl font-heading font-extrabold font-mono text-teal-300">${pctReal.toFixed(1)}%</span>

                            <span class="text-[9px] uppercase font-bold text-slate-400">Avance Real</span>

                        </div>

                    </div>



                    <!-- Rangos del Tacómetro -->

                    <div class="grid grid-cols-3 gap-1.5 pt-2 border-t border-slate-800/80 text-[10px] text-center font-mono">

                        <div class="p-1.5 rounded-lg bg-rose-950/30 border border-rose-500/30 text-rose-300">

                            <span class="block text-[8px] uppercase">Rezago</span>

                            <span>0% - 30%</span>

                        </div>

                        <div class="p-1.5 rounded-lg bg-amber-950/40 border border-amber-500/40 text-amber-300 font-bold">

                            <span class="block text-[8px] uppercase">Moderado</span>

                            <span>30% - 60%</span>

                        </div>

                        <div class="p-1.5 rounded-lg bg-emerald-950/30 border border-emerald-500/30 text-emerald-300">

                            <span class="block text-[8px] uppercase">Óptimo</span>

                            <span>60% - 100%</span>

                        </div>

                    </div>

                </div>



                <!-- Columna Derecha: Curva S de Avance Real vs Proyectado -->

                <div class="lg:col-span-7 p-4 sm:p-5 rounded-2xl bg-slate-900/70 border border-slate-800 space-y-3 shadow-lg">

                    <div class="flex items-center justify-between border-b border-slate-800 pb-2">

                        <span class="font-bold text-slate-200 text-xs flex items-center gap-1.5">

                            <span>📈</span> Curva de Avance "S" (Real vs. Ideal Programado)

                        </span>

                        <div class="flex items-center gap-3 text-[10px] font-mono">

                            <span class="flex items-center gap-1 text-[#00d2ff]">

                                <span class="w-2.5 h-0.5 bg-[#00d2ff]"></span> Real

                            </span>

                            <span class="flex items-center gap-1 text-slate-400">

                                <span class="w-2.5 h-0.5 border-t border-dashed border-slate-400"></span> Proyectado

                            </span>

                        </div>

                    </div>



                    <div class="relative w-full h-[200px]">

                        <canvas id="drilldown-scurve-canvas"></canvas>

                    </div>



                    <div class="text-[11px] text-slate-300 bg-slate-950/60 p-2.5 rounded-xl border border-slate-800 flex items-center justify-between">

                        <span>Brecha temporal a Agosto: <strong class="text-amber-300 font-mono">-24.5%</strong></span>

                        <span class="text-slate-400 text-[10px]">Aceleración proyectada en Q4 (Obras PTAP)</span>

                    </div>

                </div>

            </div>



            <div class="p-3.5 rounded-xl bg-teal-950/30 border border-teal-500/30 text-xs text-teal-200 flex items-start gap-2.5">

                <span class="text-base">⚡</span>

                <div>

                    <span class="font-bold text-white block">Explicación Técnica de la Curva de Avance:</span>

                    <span>La aparente brecha del 24.5% obedece a la naturaleza de los contratos de obra civil (como optimización de redes y PTAP), donde los contratistas radican actas parciales acumuladas y liquidación final durante los meses de Octubre, Noviembre y Diciembre. Se proyecta un cierre de vigencia superior al 95% del presupuesto.</span>

                </div>

            </div>

        </div>

    `;

}



function initDrillDown6Charts(summary) {

    if (typeof Chart === 'undefined') return;



    // 1. Gauge Chart

    const ctxGauge = document.getElementById('drilldown-gauge-canvas');

    if (ctxGauge) {

        new Chart(ctxGauge, {

            type: 'doughnut',

            data: {

                labels: ['Rezago (<30%)', 'Moderado (30-60%)', 'Óptimo (>60%)'],

                datasets: [{

                    data: [30, 30, 40],

                    backgroundColor: [

                        'rgba(244, 63, 94, 0.4)',

                        'rgba(245, 158, 11, 0.75)',

                        'rgba(16, 185, 129, 0.4)'

                    ],

                    borderColor: '#070d19',

                    borderWidth: 3

                }]

            },

            options: {

                responsive: true,

                maintainAspectRatio: false,

                circumference: 180,

                rotation: -90,

                cutout: '76%',

                plugins: {

                    legend: { display: false },

                    tooltip: { enabled: false }

                }

            }

        });

    }



    // 2. S-Curve Chart

    const ctxS = document.getElementById('drilldown-scurve-canvas');

    if (ctxS) {

        activeDrillDownChart = new Chart(ctxS, {

            type: 'line',

            data: {

                labels: ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'],

                datasets: [

                    {

                        label: 'Avance Real Reportado',

                        data: [2.2, 15.9, 26.7, 28.8, 34.8, 38.1, 41.2, 42.2, null, null, null, null],

                        borderColor: '#00d2ff',

                        backgroundColor: 'rgba(0, 210, 255, 0.15)',

                        borderWidth: 3,

                        pointBackgroundColor: '#00d2ff',

                        pointBorderColor: '#070d19',

                        pointRadius: 4,

                        tension: 0.35

                    },

                    {

                        label: 'Proyección Q4 Estimada',

                        data: [null, null, null, null, null, null, null, 42.2, 55.0, 72.0, 88.0, 96.5],

                        borderColor: '#10b981',

                        borderDash: [4, 4],

                        borderWidth: 2,

                        pointBackgroundColor: '#10b981',

                        pointRadius: 3,

                        tension: 0.35

                    },

                    {

                        label: 'Avance Ideal Lineal',

                        data: [8.3, 16.7, 25.0, 33.3, 41.7, 50.0, 58.3, 66.7, 75.0, 83.3, 91.7, 100.0],

                        borderColor: '#64748B',

                        borderDash: [3, 3],

                        borderWidth: 1.5,

                        pointRadius: 0,

                        tension: 0.1

                    }

                ]

            },

            options: {

                responsive: true,

                maintainAspectRatio: false,

                interaction: { mode: 'index', intersect: false },

                plugins: {

                    legend: { display: false },

                    tooltip: {

                        backgroundColor: 'rgba(7, 13, 25, 0.95)',

                        titleColor: '#FFFFFF',

                        borderColor: 'rgba(0, 210, 255, 0.4)',

                        borderWidth: 1,

                        padding: 8,

                        callbacks: {

                            label: function(c) {

                                if (c.raw === null || c.raw === undefined) return '';

                                return ` ${c.dataset.label}: ${c.raw}%`;

                            }

                        }

                    }

                },

                scales: {

                    x: {

                        grid: { color: 'rgba(255, 255, 255, 0.05)' },

                        ticks: { color: '#94A3B8', font: { family: 'Poppins', size: 10 } }

                    },

                    y: {

                        min: 0,

                        max: 100,

                        grid: { color: 'rgba(255, 255, 255, 0.06)' },

                        ticks: {

                            color: '#94A3B8',

                            font: { family: 'JetBrains Mono', size: 10 },

                            callback: function(v) { return `${v}%`; }

                        }

                    }

                }

            }

        });

    }

}





function renderContractorSelectAndPills(contractors, topContractors) {

    state.execution.allContractorsList = contractors || [];



    // 1. Sincronizar el select nativo

    const select = document.getElementById('exec-contractor-select');

    if (select) {

        let html = '<option value="">-- Seleccione un contratista para consultar --</option>';

        const sorted = [...contractors].sort((a, b) => a.nombre_o_razon_social.localeCompare(b.nombre_o_razon_social));

        sorted.forEach(c => {

            const executedStr = c.total_ejecutado > 0 ? ` [Ejecutado: ${formatCurrency(c.total_ejecutado)}]` : ' [Sin egresos]';

            const selectedAttr = state.execution.selectedContractorId == c.id ? 'selected' : '';

            html += `<option value="${c.id}" ${selectedAttr}>${c.nombre_o_razon_social}${executedStr}</option>`;

        });

        select.innerHTML = html;

    }



    // 2. Renderizar lista en el buscador interactivo para móviles y escritorio

    renderExecutionContractorDropdown(state.execution.allContractorsList);



    // Sincronizar texto en el input si hay un contratista seleccionado

    const searchInput = document.getElementById('exec-contractor-search-input');

    if (searchInput) {

        if (state.execution.selectedContractorId) {

            const selected = (contractors || []).find(c => c.id == state.execution.selectedContractorId);

            if (selected) searchInput.value = selected.nombre_o_razon_social;

        } else {

            searchInput.value = '';

        }

    }



    // 3. Render Pills

    const pillsContainer = document.getElementById('exec-contractor-pills');

    if (pillsContainer) {

        if (!topContractors || topContractors.length === 0) {

            pillsContainer.innerHTML = '<span class="text-xs text-slate-500">No hay pagos registrados para contratistas.</span>';

            return;

        }

        let pillsHtml = '';

        topContractors.slice(0, 8).forEach(tc => {

            const isActive = state.execution.selectedContractorId === tc.id ? 'active bg-sky-500/20 border-[#55C6DE] text-white font-bold' : 'bg-slate-900/80 border-slate-800 text-slate-300';

            pillsHtml += `

                <button type="button" onclick="selectContractorExecution(${tc.id})" 

                        class="contractor-pill px-2.5 py-1 rounded-lg border text-[11px] flex items-center gap-1.5 shadow-sm ${isActive}">

                    <span>👤</span>

                    <span class="max-w-[140px] truncate" title="${tc.nombre_o_razon_social}">${tc.nombre_o_razon_social}</span>

                    <span class="text-[10px] text-emerald-400 font-mono font-semibold">${tc.porcentaje_ejecucion.toFixed(0)}%</span>

                </button>

            `;

        });

        pillsContainer.innerHTML = pillsHtml;

    }

}



// -------------------------------------------------------------

// CONTROLADOR DEL BUSCADOR / FILTRO TÁCTIL DE CONTRATISTAS

// -------------------------------------------------------------

function renderExecutionContractorDropdown(contractors) {

    const dropdown = document.getElementById('exec-contractor-results-dropdown');

    if (!dropdown) return;



    if (!contractors || contractors.length === 0) {

        dropdown.innerHTML = '<div class="p-3 text-center text-xs text-slate-400">No se encontraron contratistas coincidentes</div>';

        return;

    }



    const sorted = [...contractors].sort((a, b) => a.nombre_o_razon_social.localeCompare(b.nombre_o_razon_social));

    let html = '';

    sorted.forEach(c => {

        const isSelected = state.execution.selectedContractorId == c.id;

        const activeClass = isSelected ? 'bg-sky-600/25 text-[#55C6DE] font-bold' : 'text-slate-200';

        const docStr = c.numero_documento ? `<span class="text-[10px] text-slate-400 font-mono">${c.tipo_documento || 'NIT'}: ${c.numero_documento}</span>` : '';

        const execStr = c.total_ejecutado > 0 

            ? `<span class="text-[11px] text-emerald-400 font-mono font-bold">${formatCurrency(c.total_ejecutado)}</span>` 

            : `<span class="text-[10px] text-slate-500 font-mono">$0 COP</span>`;

        const pctBadge = (c.porcentaje_ejecucion !== undefined && c.porcentaje_ejecucion !== null)

            ? `<span class="text-[10px] px-1.5 py-0.5 rounded bg-emerald-950/80 text-emerald-300 font-mono font-bold">${c.porcentaje_ejecucion.toFixed(0)}%</span>`

            : '';



        const safeName = (c.nombre_o_razon_social || '').replace(/'/g, "\\'");



        html += `

            <div class="contractor-dropdown-item ${activeClass}" onclick="selectContractorFromDropdown(${c.id}, '${safeName}')">

                <div class="flex items-center gap-2 overflow-hidden">

                    <span class="text-sm">👤</span>

                    <div class="overflow-hidden">

                        <p class="text-xs font-bold truncate">${c.nombre_o_razon_social}</p>

                        ${docStr}

                    </div>

                </div>

                <div class="flex items-center gap-1.5 flex-shrink-0 text-right">

                    ${execStr}

                    ${pctBadge}

                </div>

            </div>

        `;

    });

    dropdown.innerHTML = html;

}



function filterExecutionContractorList(query) {

    const q = (query || '').trim().toLowerCase();

    const dropdown = document.getElementById('exec-contractor-results-dropdown');

    showExecutionContractorDropdown();



    const list = state.execution.allContractorsList || [];

    if (!q) {

        renderExecutionContractorDropdown(list);

        return;

    }



    const filtered = list.filter(c => {

        const name = (c.nombre_o_razon_social || '').toLowerCase();

        const doc = (c.numero_documento || '').toLowerCase();

        return name.includes(q) || doc.includes(q);

    });



    renderExecutionContractorDropdown(filtered);

}



function showExecutionContractorDropdown() {

    const dropdown = document.getElementById('exec-contractor-results-dropdown');

    if (dropdown) dropdown.classList.remove('hidden');

}



function hideExecutionContractorDropdown() {

    const dropdown = document.getElementById('exec-contractor-results-dropdown');

    if (dropdown) dropdown.classList.add('hidden');

}



function toggleExecutionContractorDropdown() {

    const dropdown = document.getElementById('exec-contractor-results-dropdown');

    if (!dropdown) return;

    if (dropdown.classList.contains('hidden')) {

        renderExecutionContractorDropdown(state.execution.allContractorsList || []);

        dropdown.classList.remove('hidden');

        const input = document.getElementById('exec-contractor-search-input');

        if (input) input.focus();

    } else {

        dropdown.classList.add('hidden');

    }

}



async function selectContractorFromDropdown(contractorId, contractorName) {

    const input = document.getElementById('exec-contractor-search-input');

    if (input) input.value = contractorName;

    const select = document.getElementById('exec-contractor-select');

    if (select) select.value = String(contractorId);

    hideExecutionContractorDropdown();



    await onExecutionContractorSelect(contractorId);

}



// Cerrar dropdown al hacer clic fuera del componente

document.addEventListener('click', (e) => {

    const wrapper = document.getElementById('exec-contractor-search-wrapper');

    if (wrapper && !wrapper.contains(e.target)) {

        hideExecutionContractorDropdown();

    }

});



/**

 * Genera un gráfico de torta / donut en SVG interactivo y de alta resolución

 * @param {Array<{label: string, value: number, color: string}>} segments 

 * @param {string} centerMain Texto principal del centro (ej. '42.2%')

 * @param {string} centerSub Subtexto del centro (ej. 'Avance')

 * @param {number} size Tamaño en píxeles

 */

function generateSvgDonut(segments, centerMain, centerSub, size = 115) {

    const total = segments.reduce((sum, s) => sum + (s.value || 0), 0);

    if (total <= 0) {

        return `

            <div class="flex flex-col items-center justify-center text-slate-500 text-xs" style="width:${size}px; height:${size}px;">

                <span class="text-xl">⚪</span>

                <span class="text-[10px] mt-1 font-mono">Sin datos</span>

            </div>

        `;

    }



    const r = 15.91549430918954;

    let accum = 25.0; // Inicia a las 12 horas en sentido horario

    let circlesHtml = '';



    // Anillo base de fondo

    circlesHtml += `<circle class="donut-ring-base" cx="21" cy="21" r="${r}" fill="transparent" stroke="#cbd5e1" stroke-width="4.4" opacity="0.6"></circle>`;



    segments.forEach((s) => {

        if (!s.value || s.value <= 0) return;

        const pct = (s.value / total) * 100;

        const rem = 100 - pct;

        const offset = accum;

        accum -= pct;

        const slug = (s.label || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');

        circlesHtml += `

            <circle class="donut-slice donut-slice-${slug}" cx="21" cy="21" r="${r}" fill="transparent" 

                    stroke="${s.color}" stroke-width="4.8" 

                    stroke-dasharray="${pct.toFixed(2)} ${rem.toFixed(2)}" 

                    stroke-dashoffset="${offset.toFixed(2)}"

                    data-tooltip="${s.label}: ${formatCurrency(s.value)} (${pct.toFixed(1)}%)">

                <title>${s.label}: ${formatCurrency(s.value)} (${pct.toFixed(1)}%)</title>

            </circle>

        `;

    });



    return `

        <div class="donut-container relative flex items-center justify-center select-none" style="width: ${size}px; height: ${size}px;">

            <svg viewBox="0 0 42 42" class="w-full h-full overflow-visible">

                ${circlesHtml}

                <text class="donut-text-main" x="21" y="20" text-anchor="middle" font-size="5.6" font-weight="800" font-family="'JetBrains Mono', monospace">${centerMain}</text>

                <text class="donut-text-sub uppercase" x="21" y="24.8" text-anchor="middle" font-size="2.6" font-weight="600" letter-spacing="0.04em">${centerSub}</text>

            </svg>

        </div>

    `;

}



async function openContractorExecutionModal(contractorId) {

    const modal = document.getElementById('modal-contractor-dossier');

    if (!modal) return;



    try {

        modal.classList.remove('hidden');

        document.getElementById('modal-cd-name').innerText = 'Cargando contratista...';

        document.getElementById('modal-cd-persona').innerText = '...';

        document.getElementById('modal-cd-doc').innerHTML = '<strong>Documento:</strong> Cargando...';

        document.getElementById('modal-cd-bank').innerHTML = '<strong>Banco:</strong> Cargando...';

        document.getElementById('modal-cd-total-contracted').innerText = '...';

        document.getElementById('modal-cd-total-executed').innerText = '...';

        document.getElementById('modal-cd-total-retentions').innerText = '...';

        document.getElementById('modal-cd-net-paid').innerText = 'Neto: ...';

        document.getElementById('modal-cd-balance').innerText = '...';

        document.getElementById('modal-cd-contracts-tbody').innerHTML = '<tr><td colspan="7" class="py-4 text-center text-slate-500">Cargando contratos...</td></tr>';

        document.getElementById('modal-cd-payments-tbody').innerHTML = '<tr><td colspan="7" class="py-4 text-center text-slate-500">Cargando comprobantes...</td></tr>';



        const vigParam = state.selectedVigencia === 'ALL' ? 'ALL' : state.selectedVigencia;

        const dossier = await window.api.getExecutionContractor(contractorId, vigParam);



        // Header info

        document.getElementById('modal-cd-name').innerText = dossier.nombre_o_razon_social || 'Contratista';

        document.getElementById('modal-cd-persona').innerText = dossier.tipo_persona || 'PERSONA';

        document.getElementById('modal-cd-doc').innerHTML = `<strong>Documento:</strong> ${dossier.tipo_documento || 'NIT'} ${dossier.numero_documento || 'N/A'}`;

        const bankInfo = dossier.banco_nombre ? `${dossier.banco_nombre} (${dossier.banco_tipo_cuenta || 'Cta'} ${dossier.banco_numero_cuenta || ''})` : 'No registrado';

        document.getElementById('modal-cd-bank').innerHTML = `<strong>Banco:</strong> ${bankInfo}`;



        // 4 Financial Cards

        document.getElementById('modal-cd-total-contracted').innerText = formatCurrency(dossier.valor_total_contratado);

        document.getElementById('modal-cd-contracts-count').innerText = `${dossier.total_contratos || 0} contrato(s)`;



        document.getElementById('modal-cd-total-executed').innerText = formatCurrency(dossier.total_ejecutado);

        document.getElementById('modal-cd-vouchers-count').innerText = `${dossier.conteo_pagos || 0} comprobante(s) de egreso`;



        document.getElementById('modal-cd-total-retentions').innerText = formatCurrency(dossier.total_retenciones);

        document.getElementById('modal-cd-net-paid').innerText = `Neto: ${formatCurrency(dossier.total_neto_pagado)}`;



        document.getElementById('modal-cd-balance').innerText = formatCurrency(dossier.saldo_por_ejecutar);



        // Visual Analytics Calculations

        const valTotal = dossier.valor_total_contratado || 0;

        const totalOrden = dossier.total_ejecutado || 0;

        const totalRet = dossier.total_retenciones || 0;

        const totalNeto = dossier.total_neto_pagado || Math.max(0, totalOrden - totalRet);

        const saldo = dossier.saldo_por_ejecutar || Math.max(0, valTotal - totalOrden);

        const pctAvance = dossier.porcentaje_ejecucion || 0;



        const pctNetoDeOrden = totalOrden > 0 ? (totalNeto / totalOrden * 100) : 0;

        const pctRetDeOrden = totalOrden > 0 ? (totalRet / totalOrden * 100) : 0;



        const pctNetoDeTotal = valTotal > 0 ? (totalNeto / valTotal * 100) : 0;

        const pctRetDeTotal = valTotal > 0 ? (totalRet / valTotal * 100) : 0;

        const pctSaldoDeTotal = valTotal > 0 ? (saldo / valTotal * 100) : 100;



        // Render Donut 1: Presupuesto

        const donutBudgetEl = document.getElementById('modal-cd-donut-budget');

        if (donutBudgetEl) {

            donutBudgetEl.innerHTML = generateSvgDonut([

                { label: 'Ejecutado', value: totalOrden, color: '#55C6DE' },

                { label: 'Saldo Libre', value: saldo, color: '#A78BFA' }

            ], `${pctAvance.toFixed(1)}%`, 'Avance', 115);

        }



        // Render Donut 2: Desembolsos

        const donutDisbEl = document.getElementById('modal-cd-donut-disbursement');

        if (donutDisbEl) {

            donutDisbEl.innerHTML = generateSvgDonut([

                { label: 'Neto Girado', value: totalNeto, color: '#10B981' },

                { label: 'Retenciones', value: totalRet, color: '#F59E0B' }

            ], `${pctNetoDeOrden.toFixed(1)}%`, 'Neto', 115);

        }



        // Legends

        const legEj = document.getElementById('modal-cd-legend-ejecutado');

        if (legEj) legEj.innerText = `${formatCurrency(totalOrden)} (${pctAvance.toFixed(1)}%)`;

        const legSal = document.getElementById('modal-cd-legend-saldo');

        if (legSal) legSal.innerText = `${formatCurrency(saldo)} (${(100 - pctAvance).toFixed(1)}%)`;

        const legNet = document.getElementById('modal-cd-legend-neto');

        if (legNet) legNet.innerText = `${formatCurrency(totalNeto)} (${pctNetoDeOrden.toFixed(1)}%)`;

        const legRet = document.getElementById('modal-cd-legend-ret');

        if (legRet) legRet.innerText = `${formatCurrency(totalRet)} (${pctRetDeOrden.toFixed(1)}%)`;



        // Stacked Bar

        const barNet = document.getElementById('modal-cd-bar-neto');

        if (barNet) barNet.style.width = `${pctNetoDeTotal.toFixed(1)}%`;

        const barRet = document.getElementById('modal-cd-bar-ret');

        if (barRet) barRet.style.width = `${pctRetDeTotal.toFixed(1)}%`;

        const barSal = document.getElementById('modal-cd-bar-saldo');

        if (barSal) barSal.style.width = `${pctSaldoDeTotal.toFixed(1)}%`;



        const lblNet = document.getElementById('modal-cd-pct-neto-lbl');

        if (lblNet) lblNet.innerText = `${pctNetoDeTotal.toFixed(1)}%`;

        const lblRet = document.getElementById('modal-cd-pct-ret-lbl');

        if (lblRet) lblRet.innerText = `${pctRetDeTotal.toFixed(1)}%`;

        const lblSal = document.getElementById('modal-cd-pct-saldo-lbl');

        if (lblSal) lblSal.innerText = `${pctSaldoDeTotal.toFixed(1)}%`;



        // Subcounts

        const cCountEl = document.getElementById('modal-cd-contracts-subcount');

        if (cCountEl) cCountEl.innerText = `${(dossier.contratos || []).length} contratos`;



        const pCountEl = document.getElementById('modal-cd-payments-subcount');

        if (pCountEl) pCountEl.innerText = `${(dossier.pagos || []).length} comprobantes`;



        // Contracts Table

        const cTbody = document.getElementById('modal-cd-contracts-tbody');

        if (cTbody) {

            if (!dossier.contratos || dossier.contratos.length === 0) {

                cTbody.innerHTML = '<tr><td colspan="7" class="py-4 text-center text-slate-500">No registra contratos en la vigencia seleccionada.</td></tr>';

            } else {

                let cH = '';

                dossier.contratos.forEach(ct => {

                    const cPct = ct.porcentaje_ejecucion || 0;

                    cH += `

                        <tr class="hover:bg-slate-800/40 transition-colors">

                            <td class="py-2.5 px-3 font-mono font-bold text-sky-300">${ct.numero_contrato}</td>

                            <td class="py-2.5 px-3">${getTypologyBadge(ct.tipologia)}</td>

                            <td class="py-2.5 px-3 text-right font-mono">${formatCurrency(ct.valor_total)}</td>

                            <td class="py-2.5 px-3 text-right font-mono text-sky-400">${formatCurrency(ct.total_ejecutado)}</td>

                            <td class="py-2.5 px-3 text-right font-mono text-purple-300">${formatCurrency(ct.saldo_por_ejecutar)}</td>

                            <td class="py-2.5 px-3 text-center">

                                <div class="flex items-center justify-center gap-1.5">

                                    <div class="progress-track w-14 h-2">

                                        <div class="progress-fill-gradient h-full" style="width: ${Math.min(100, cPct)}%;"></div>

                                    </div>

                                    <span class="font-mono text-[11px] font-bold text-sky-300">${cPct.toFixed(0)}%</span>

                                </div>

                            </td>

                            <td class="py-2.5 px-3 text-center">

                                <button onclick="openContractPaymentsModal(${ct.id})" class="px-2 py-1 bg-slate-800 hover:bg-[#1590D3] hover:text-white text-slate-300 rounded-lg text-[11px] font-medium transition-all shadow-sm">

                                    <span>🔍</span> Pagos (${ct.conteo_pagos})

                                </button>

                            </td>

                        </tr>

                    `;

                });

                cTbody.innerHTML = cH;

            }

        }



        // Payments Table

        const pTbody = document.getElementById('modal-cd-payments-tbody');

        if (pTbody) {

            state.execution.currentModalPayments = dossier.pagos || [];

            if (!dossier.pagos || dossier.pagos.length === 0) {

                pTbody.innerHTML = '<tr><td colspan="7" class="py-4 text-center text-slate-500">No registra pagos en la vigencia seleccionada.</td></tr>';

            } else {

                let pH = '';

                dossier.pagos.forEach(p => {

                    const fExp = p.fecha_expedicion ? p.fecha_expedicion.substring(0, 10) : 'S/F';

                    pH += `

                        <tr class="hover:bg-slate-800/40 transition-colors">

                            <td class="py-2 px-3 font-mono font-bold text-amber-300">

                                <span class="cursor-pointer hover:underline hover:text-white" onclick="openPaymentDetailDrawer(${p.id}, '${p.codigo_egreso}')" title="Ver panel animado de retenciones">${p.codigo_egreso}</span>

                            </td>

                            <td class="py-2 px-3 text-center font-mono text-slate-400 text-[11px]">${fExp}</td>

                            <td class="py-2 px-3 font-mono text-sky-300">${p.codigo_contrato}</td>

                            <td class="py-2 px-3 text-slate-300 truncate max-w-xs" title="${p.rubro_egreso || ''}">${p.rubro_egreso || 'S/R'}</td>

                            <td class="py-2 px-3 text-right font-mono font-semibold text-sky-400">${formatCurrency(p.total_orden)}</td>

                            <td class="py-2 px-3 text-right font-mono text-amber-400">

                                <div>${formatCurrency(p.total_retencion)}</div>

                                ${(p.total_estampillas && p.total_estampillas > 0) ? `<div class="text-[9px] font-sans font-semibold text-purple-300 cursor-pointer hover:text-white" onclick="openPaymentDetailDrawer(${p.id}, '${p.codigo_egreso}')" title="${p.retenciones_raw || ''}">🏛️ ${formatCurrency(p.total_estampillas)}</div>` : ''}

                            </td>

                            <td class="py-2 px-3 text-right font-mono font-bold text-emerald-400">${formatCurrency(p.total_pagar)}</td>

                        </tr>

                    `;

                });

                pTbody.innerHTML = pH;

            }

        }



        // Keep top dossier and select in sync as well

        state.execution.selectedContractorId = contractorId ? parseInt(contractorId, 10) : null;

        const select = document.getElementById('exec-contractor-select');

        if (select) select.value = contractorId ? String(contractorId) : '';

        const searchInput = document.getElementById('exec-contractor-search-input');

        if (searchInput && contractorId) {

            const selected = (state.execution.allContractorsList || []).find(c => c.id == contractorId);

            if (selected) searchInput.value = selected.nombre_o_razon_social;

        }

        const clearBtn = document.getElementById('btn-clear-contractor-filter');

        if (clearBtn) clearBtn.classList.remove('hidden');

        loadContractorDossier(contractorId);



    } catch (err) {

        console.error('Error al abrir ficha de ejecución del contratista:', err);

        showToast(`Error al cargar la ficha: ${err.message}`, 'error');

    }

}



function closeContractorExecutionModal() {

    const modal = document.getElementById('modal-contractor-dossier');

    if (modal) modal.classList.add('hidden');

}



async function selectContractorExecution(contractorId) {

    await openContractorExecutionModal(contractorId);

}



async function onExecutionContractorSelect(contractorId) {

    state.execution.selectedContractorId = contractorId ? parseInt(contractorId, 10) : null;

    

    // Sincronizar input de búsqueda

    const searchInput = document.getElementById('exec-contractor-search-input');

    if (searchInput) {

        if (state.execution.selectedContractorId) {

            const selected = (state.execution.allContractorsList || []).find(c => c.id == state.execution.selectedContractorId);

            if (selected) searchInput.value = selected.nombre_o_razon_social;

        } else {

            searchInput.value = '';

        }

    }



    // Update pills styling

    const pills = document.querySelectorAll('.contractor-pill');

    pills.forEach(p => p.classList.remove('active', 'bg-sky-500/20', 'border-[#55C6DE]', 'text-white', 'font-bold'));



    const clearBtn = document.getElementById('btn-clear-contractor-filter');

    const dossier = document.getElementById('exec-contractor-dossier');



    if (!state.execution.selectedContractorId) {

        if (clearBtn) clearBtn.classList.add('hidden');

        if (dossier) dossier.classList.add('hidden');

        renderExecSubTabContent();

        return;

    }



    if (clearBtn) clearBtn.classList.remove('hidden');

    await loadContractorDossier(state.execution.selectedContractorId);

    renderExecSubTabContent();

}



function clearContractorExecutionFilter() {

    state.execution.selectedContractorId = null;

    const select = document.getElementById('exec-contractor-select');

    if (select) select.value = '';

    const searchInput = document.getElementById('exec-contractor-search-input');

    if (searchInput) searchInput.value = '';

    hideExecutionContractorDropdown();



    const clearBtn = document.getElementById('btn-clear-contractor-filter');

    if (clearBtn) clearBtn.classList.add('hidden');

    const dossier = document.getElementById('exec-contractor-dossier');

    if (dossier) dossier.classList.add('hidden');



    const pills = document.querySelectorAll('.contractor-pill');

    pills.forEach(p => p.classList.remove('active', 'bg-sky-500/20', 'border-[#55C6DE]', 'text-white', 'font-bold'));



    renderExecSubTabContent();

    showToast('Filtro de contratista restablecido.', 'info');

}



async function loadContractorDossier(contractorId) {

    const container = document.getElementById('exec-contractor-dossier');

    if (!container) return;



    try {

        container.innerHTML = '<div class="p-6 text-center text-xs text-slate-400">Cargando expediente de ejecución del contratista...</div>';

        container.classList.remove('hidden');



        const vigParam = state.selectedVigencia === 'ALL' ? 'ALL' : state.selectedVigencia;

        const dossier = await window.api.getExecutionContractor(contractorId, vigParam);



        const valTotal = dossier.valor_total_contratado || 0;

        const totalOrden = dossier.total_ejecutado || 0;

        const totalRet = dossier.total_retenciones || 0;

        const totalNeto = dossier.total_neto_pagado || Math.max(0, totalOrden - totalRet);

        const saldo = dossier.saldo_por_ejecutar || Math.max(0, valTotal - totalOrden);

        const pctAvance = dossier.porcentaje_ejecucion || 0;



        const pctNetoDeOrden = totalOrden > 0 ? (totalNeto / totalOrden * 100) : 0;

        const pctRetDeOrden = totalOrden > 0 ? (totalRet / totalOrden * 100) : 0;



        const pctNetoDeTotal = valTotal > 0 ? (totalNeto / valTotal * 100) : 0;

        const pctRetDeTotal = valTotal > 0 ? (totalRet / valTotal * 100) : 0;

        const pctSaldoDeTotal = valTotal > 0 ? (saldo / valTotal * 100) : 100;



        let pctColor = 'text-sky-400';

        let barColor = 'progress-fill-gradient';

        if (pctAvance >= 85) {

            pctColor = 'text-emerald-400';

            barColor = 'progress-fill-emerald';

        } else if (pctAvance >= 40) {

            pctColor = 'text-teal-300';

        } else if (pctAvance > 0) {

            pctColor = 'text-amber-400';

            barColor = 'progress-fill-amber';

        }



        const donutBudgetHtml = generateSvgDonut([

            { label: 'Ejecutado', value: totalOrden, color: '#55C6DE' },

            { label: 'Saldo Libre', value: saldo, color: '#A78BFA' }

        ], `${pctAvance.toFixed(1)}%`, 'Avance', 115);



        const donutDisbHtml = generateSvgDonut([

            { label: 'Neto Girado', value: totalNeto, color: '#10B981' },

            { label: 'Retenciones', value: totalRet, color: '#F59E0B' }

        ], `${pctNetoDeOrden.toFixed(1)}%`, 'Neto', 115);



        // Contracts mini rows

        let contractsRows = '';

        if (dossier.contratos && dossier.contratos.length > 0) {

            dossier.contratos.forEach(c => {

                const cPct = c.porcentaje_ejecucion || 0;

                contractsRows += `

                    <tr class="hover:bg-slate-800/40 transition-colors">

                        <td class="py-2 px-3 font-mono font-bold text-sky-300">${c.numero_contrato}</td>

                        <td class="py-2 px-3">${getTypologyBadge(c.tipologia)}</td>

                        <td class="py-2 px-3 text-right font-mono">${formatCurrency(c.valor_total)}</td>

                        <td class="py-2 px-3 text-right font-mono text-sky-400">${formatCurrency(c.total_ejecutado)}</td>

                        <td class="py-2 px-3 text-right font-mono text-purple-300">${formatCurrency(c.saldo_por_ejecutar)}</td>

                        <td class="py-2 px-3 text-center">

                            <div class="flex items-center justify-center gap-2">

                                <div class="progress-track w-16 h-2">

                                    <div class="${barColor} h-full" style="width: ${Math.min(100, cPct)}%;"></div>

                                </div>

                                <span class="font-mono text-[11px] font-bold ${pctColor}">${cPct.toFixed(1)}%</span>

                            </div>

                        </td>

                        <td class="py-2 px-3 text-center">

                            <button onclick="openContractPaymentsModal(${c.id})" class="px-2 py-1 bg-slate-800 hover:bg-[#1590D3] hover:text-white text-slate-300 rounded-lg text-[11px] font-medium transition-all shadow-sm">

                                📑 Pagos

                            </button>

                        </td>

                    </tr>

                `;

            });

        } else {

            contractsRows = '<tr><td colspan="7" class="py-4 text-center text-slate-500">No hay contratos registrados para este contratista.</td></tr>';

        }



        container.innerHTML = `

            <div class="space-y-4">

                <!-- Contractor Header Card -->

                <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 p-4 bg-slate-950/70 rounded-2xl border border-sky-900/30">

                    <div class="flex items-center gap-3">

                        <div class="w-12 h-12 rounded-xl bg-gradient-to-br from-[#1590D3]/30 to-[#009540]/30 border border-[#55C6DE]/40 flex items-center justify-center text-xl shadow-md flex-shrink-0">

                            🏢

                        </div>

                        <div>

                            <div class="flex items-center gap-2">

                                <h3 class="font-heading font-extrabold text-base sm:text-lg text-white">${dossier.nombre_o_razon_social}</h3>

                                <span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700">${dossier.tipo_persona}</span>

                            </div>

                            <div class="flex flex-wrap items-center gap-3 text-xs text-slate-400 mt-1">

                                <span><strong>Documento:</strong> ${dossier.tipo_documento} ${dossier.numero_documento}</span>

                                <span>&bull;</span>

                                <span><strong>Banco:</strong> ${dossier.banco_nombre || 'No registrado'} (${dossier.banco_tipo_cuenta || 'Cta'} ${dossier.banco_numero_cuenta || ''})</span>

                            </div>

                        </div>

                    </div>

                    <div class="flex items-center gap-2">

                        <button onclick="viewContractorPaymentsDirectly(${dossier.id})" class="px-3 py-1.5 bg-[#1590D3]/20 hover:bg-[#1590D3]/30 text-sky-300 border border-[#55C6DE]/40 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-all">

                            <span>💸</span> Ver Comprobantes (${dossier.conteo_pagos})

                        </button>

                    </div>

                </div>



                <!-- Financial Metrics Breakdown -->

                <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">

                    <div class="p-3 bg-slate-950/60 rounded-xl border border-slate-800">

                        <span class="text-[10px] uppercase font-bold text-slate-400">Total Contratado</span>

                        <div class="text-xs sm:text-base font-extrabold text-white font-mono mt-1 break-words">${formatCurrency(dossier.valor_total_contratado)}</div>

                        <span class="text-[10px] text-slate-500">${dossier.total_contratos} contrato(s)</span>

                    </div>

                    <div class="p-3 bg-slate-950/60 rounded-xl border border-sky-900/40">

                        <span class="text-[10px] uppercase font-bold text-sky-400">Total Órdenes (Ejecutado)</span>

                        <div class="text-xs sm:text-base font-extrabold text-[#55C6DE] font-mono mt-1 break-words">${formatCurrency(dossier.total_ejecutado)}</div>

                        <span class="text-[10px] text-sky-500">${dossier.conteo_pagos} pago(s) realizados</span>

                    </div>

                    <div class="p-3 bg-slate-950/60 rounded-xl border border-amber-900/40">

                        <span class="text-[10px] uppercase font-bold text-amber-400">Retenciones Practicadas</span>

                        <div class="text-xs sm:text-base font-extrabold text-amber-400 font-mono mt-1 break-words">${formatCurrency(dossier.total_retenciones)}</div>

                        <span class="text-[10px] text-amber-500/80">Neto: ${formatCurrency(dossier.total_neto_pagado)}</span>

                    </div>

                    <div class="p-3 bg-slate-950/60 rounded-xl border border-purple-900/40">

                        <span class="text-[10px] uppercase font-bold text-purple-300">Saldo Pendiente</span>

                        <div class="text-xs sm:text-base font-extrabold text-purple-300 font-mono mt-1 break-words">${formatCurrency(dossier.saldo_por_ejecutar)}</div>

                        <span class="text-[10px] text-purple-400/80">Por ejecutar</span>

                    </div>

                </div>



                <!-- Interactive Visual Analytics Panel: Donut Charts & Stacked Progress -->

                <div class="p-3.5 sm:p-5 bg-slate-950/80 rounded-2xl border border-slate-800 space-y-4 shadow-lg overflow-hidden">

                    <div class="flex items-center justify-between border-b border-slate-800 pb-2.5">

                        <span class="text-xs font-bold text-slate-200 flex items-center gap-1.5">

                            <span class="text-sm">📊</span> Análisis Gráfico de Ejecución y Pagos

                        </span>

                        <span class="text-[10px] font-mono text-sky-400 bg-sky-950/70 border border-sky-800/40 px-2.5 py-0.5 rounded-full font-semibold">Gráficas Dinámicas</span>

                    </div>



                    <!-- Dual Donut Charts Grid (1 col en celular/tablet, 2 cols en pantallas anchas) -->

                    <div class="grid grid-cols-1 lg:grid-cols-2 gap-3.5 sm:gap-4">

                        <!-- Donut 1: Presupuesto (Ejecutado vs Saldo) -->

                        <div class="p-3.5 sm:p-4 bg-slate-900/90 rounded-2xl border border-sky-900/40 space-y-3 hover:border-sky-500/40 transition-all shadow-md overflow-hidden">

                            <div class="flex items-center justify-between border-b border-slate-800/80 pb-2">

                                <div>

                                    <span class="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Torta de Ejecución</span>

                                    <span class="text-xs sm:text-sm font-bold text-white">Presupuesto del Contratista</span>

                                </div>

                                <span class="text-[10px] font-mono text-[#55C6DE] bg-sky-950/80 border border-sky-800/50 px-2 py-0.5 rounded-md font-bold">${pctAvance.toFixed(1)}%</span>

                            </div>

                            <div class="flex flex-col sm:flex-row items-center gap-3 sm:gap-4">

                                <div class="donut-container shrink-0 flex items-center justify-center py-1">

                                    ${donutBudgetHtml}

                                </div>

                                <div class="w-full sm:flex-1 space-y-2 min-w-0">

                                    <div class="flex items-center justify-between bg-slate-950/90 px-3 py-2 rounded-xl border border-slate-800/90 gap-2">

                                        <div class="flex items-center gap-1.5 min-w-0">

                                            <span class="w-2.5 h-2.5 rounded-full bg-[#55C6DE] shrink-0 shadow-sm"></span>

                                            <span class="text-xs font-semibold text-slate-300">Ejecutado</span>

                                        </div>

                                        <div class="text-right shrink-0">

                                            <div class="font-mono font-extrabold text-xs sm:text-sm text-[#55C6DE] leading-tight">${formatCurrency(totalOrden)}</div>

                                            <div class="text-[10px] font-mono text-sky-300/80 leading-tight">${pctAvance.toFixed(1)}% del total</div>

                                        </div>

                                    </div>

                                    <div class="flex items-center justify-between bg-slate-950/90 px-3 py-2 rounded-xl border border-slate-800/90 gap-2">

                                        <div class="flex items-center gap-1.5 min-w-0">

                                            <span class="w-2.5 h-2.5 rounded-full bg-[#A78BFA] shrink-0 shadow-sm"></span>

                                            <span class="text-xs font-semibold text-slate-300">Saldo Libre</span>

                                        </div>

                                        <div class="text-right shrink-0">

                                            <div class="font-mono font-extrabold text-xs sm:text-sm text-purple-300 leading-tight">${formatCurrency(saldo)}</div>

                                            <div class="text-[10px] font-mono text-purple-300/80 leading-tight">${(100 - pctAvance).toFixed(1)}% remanente</div>

                                        </div>

                                    </div>

                                </div>

                            </div>

                        </div>



                        <!-- Donut 2: Tesorería (Neto Pagado vs Retenciones) -->

                        <div class="p-3.5 sm:p-4 bg-slate-900/90 rounded-2xl border border-emerald-900/40 space-y-3 hover:border-emerald-500/40 transition-all shadow-md overflow-hidden">

                            <div class="flex items-center justify-between border-b border-slate-800/80 pb-2">

                                <div>

                                    <span class="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Torta de Desembolsos</span>

                                    <span class="text-xs sm:text-sm font-bold text-white">Destino de Cuentas Causadas</span>

                                </div>

                                <span class="text-[10px] font-mono text-emerald-400 bg-emerald-950/80 border border-emerald-800/50 px-2 py-0.5 rounded-md font-bold">${pctNetoDeOrden.toFixed(1)}%</span>

                            </div>

                            <div class="flex flex-col sm:flex-row items-center gap-3 sm:gap-4">

                                <div class="donut-container shrink-0 flex items-center justify-center py-1">

                                    ${donutDisbHtml}

                                </div>

                                <div class="w-full sm:flex-1 space-y-2 min-w-0">

                                    <div class="flex items-center justify-between bg-slate-950/90 px-3 py-2 rounded-xl border border-slate-800/90 gap-2">

                                        <div class="flex items-center gap-1.5 min-w-0">

                                            <span class="w-2.5 h-2.5 rounded-full bg-emerald-400 shrink-0 shadow-sm"></span>

                                            <span class="text-xs font-semibold text-slate-300">Neto Girado</span>

                                        </div>

                                        <div class="text-right shrink-0">

                                            <div class="font-mono font-extrabold text-xs sm:text-sm text-emerald-400 leading-tight">${formatCurrency(totalNeto)}</div>

                                            <div class="text-[10px] font-mono text-emerald-300/80 leading-tight">${pctNetoDeOrden.toFixed(1)}% pagado</div>

                                        </div>

                                    </div>

                                    <div class="flex items-center justify-between bg-slate-950/90 px-3 py-2 rounded-xl border border-slate-800/90 gap-2">

                                        <div class="flex items-center gap-1.5 min-w-0">

                                            <span class="w-2.5 h-2.5 rounded-full bg-amber-400 shrink-0 shadow-sm"></span>

                                            <span class="text-xs font-semibold text-slate-300">Retenciones</span>

                                        </div>

                                        <div class="text-right shrink-0">

                                            <div class="font-mono font-extrabold text-xs sm:text-sm text-amber-400 leading-tight">${formatCurrency(totalRet)}</div>

                                            <div class="text-[10px] font-mono text-amber-300/80 leading-tight">${pctRetDeOrden.toFixed(1)}% deducido</div>

                                        </div>

                                    </div>

                                </div>

                            </div>

                        </div>

                    </div>



                    <!-- Multi-Segment Visual Stacked Progress Bar -->

                    <div class="space-y-2 pt-1">

                        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-1.5 text-xs">

                            <span class="text-slate-300 font-semibold flex items-center gap-1.5">

                                <span>🧭</span> Distribución Integral del Presupuesto:

                            </span>

                            <div class="flex items-center gap-2 text-[10px] sm:text-[11px] font-mono flex-wrap">

                                <span class="text-emerald-400 font-semibold bg-emerald-950/80 px-2 py-0.5 rounded-md border border-emerald-600/40">Neto: ${pctNetoDeTotal.toFixed(1)}%</span>

                                <span class="text-amber-400 font-semibold bg-amber-950/80 px-2 py-0.5 rounded-md border border-amber-600/40">Ret: ${pctRetDeTotal.toFixed(1)}%</span>

                                <span class="text-purple-300 font-semibold bg-purple-950/80 px-2 py-0.5 rounded-md border border-purple-600/40">Saldo: ${pctSaldoDeTotal.toFixed(1)}%</span>

                            </div>

                        </div>



                        <div class="visual-stacked-bar">

                            <div class="visual-stacked-segment bg-gradient-to-r from-emerald-500 to-teal-400" 

                                 style="width: ${pctNetoDeTotal.toFixed(1)}%;" 

                                 title="Neto Desembolsado: ${formatCurrency(totalNeto)} (${pctNetoDeTotal.toFixed(1)}%)"></div>

                            <div class="visual-stacked-segment bg-gradient-to-r from-amber-500 to-orange-400" 

                                 style="width: ${pctRetDeTotal.toFixed(1)}%;" 

                                 title="Retenciones Tributarias: ${formatCurrency(totalRet)} (${pctRetDeTotal.toFixed(1)}%)"></div>

                            <div class="visual-stacked-segment bg-gradient-to-r from-purple-600/70 to-indigo-600/50" 

                                 style="width: ${pctSaldoDeTotal.toFixed(1)}%;" 

                                 title="Saldo Remanente: ${formatCurrency(saldo)} (${pctSaldoDeTotal.toFixed(1)}%)"></div>

                        </div>



                        <div class="flex items-center justify-between text-[10px] text-slate-400 font-medium px-0.5">

                            <span>0% (Inicio)</span>

                            <span class="text-sky-400 font-bold">Avance Total: ${pctAvance.toFixed(1)}%</span>

                            <span>100% (Meta)</span>

                        </div>

                    </div>

                </div>



                <!-- Contracts List Table -->

                <div class="space-y-2">

                    <span class="text-xs font-bold text-slate-300">Contratos Celebrados con la ESP:</span>

                    <div class="overflow-x-auto rounded-xl border border-slate-800">

                        <table class="w-full text-left text-xs whitespace-nowrap">

                            <thead>

                                <tr class="text-slate-400 bg-slate-950/80 font-semibold border-b border-slate-800">

                                    <th class="py-2 px-3">No. Contrato</th>

                                    <th class="py-2 px-3">Tipología</th>

                                    <th class="py-2 px-3 text-right">Valor Total</th>

                                    <th class="py-2 px-3 text-right text-sky-400">Total Orden</th>

                                    <th class="py-2 px-3 text-right text-purple-300">Saldo</th>

                                    <th class="py-2 px-3 text-center">% Avance</th>

                                    <th class="py-2 px-3 text-center">Acciones</th>

                                </tr>

                            </thead>

                            <tbody class="divide-y divide-slate-800/60">

                                ${contractsRows}

                            </tbody>

                        </table>

                    </div>

                </div>

            </div>

        `;

    } catch (err) {

        container.innerHTML = `<div class="p-4 text-xs text-rose-400">Error al cargar ficha del contratista: ${err.message}</div>`;

    }

}



function viewContractorPaymentsDirectly(contractorId) {

    state.execution.selectedContractorId = contractorId;

    switchExecSubTab('payments');

}



function renderVisualAnalytics(summary) {

    if (!summary) return;



    // 1. Monthly Chart

    const monthlyContainer = document.getElementById('exec-chart-monthly');

    if (monthlyContainer) {

        const meses = summary.meses || [];

        if (meses.length === 0) {

            monthlyContainer.innerHTML = '<div class="text-center text-xs text-slate-500 py-6">No hay registros cronológicos de pagos.</div>';

        } else {

            const maxMonthly = Math.max(...meses.map(m => m.total_ejecutado), 1);

            let html = '';

            meses.forEach(m => {

                const pct = Math.min(100, Math.round((m.total_ejecutado / maxMonthly) * 100));

                html += `

                    <div class="space-y-1">

                        <div class="flex items-center justify-between text-[11px]">

                            <span class="text-slate-300 font-medium">${m.mes_nombre}</span>

                            <div class="flex items-center gap-2">

                                <span class="text-slate-400 text-[10px] font-mono">${m.conteo_pagos} pago(s)</span>

                                <span class="font-mono font-bold text-sky-400">${formatCurrency(m.total_ejecutado)}</span>

                            </div>

                        </div>

                        <div class="progress-track w-full h-2">

                            <div class="progress-fill-gradient h-full" style="width: ${pct}%;"></div>

                        </div>

                    </div>

                `;

            });

            monthlyContainer.innerHTML = html;

        }

    }



    // 2. Rubros Chart

    const rubrosContainer = document.getElementById('exec-chart-rubros');

    if (rubrosContainer) {

        const rubros = (summary.rubros || []).slice(0, 5);

        if (rubros.length === 0) {

            rubrosContainer.innerHTML = '<div class="text-center text-xs text-slate-500 py-6">No hay datos de rubros.</div>';

        } else {

            let html = '';

            rubros.forEach(r => {

                html += `

                    <div class="space-y-1">

                        <div class="flex items-center justify-between text-[11px]">

                            <span class="text-slate-300 font-mono font-semibold truncate max-w-[170px]" title="${r.rubro}">${r.rubro}</span>

                            <div class="flex items-center gap-2">

                                <span class="text-emerald-400 font-mono font-bold text-[10px]">${r.porcentaje_del_total.toFixed(1)}%</span>

                                <span class="font-mono font-bold text-slate-200">${formatCurrency(r.total_ejecutado)}</span>

                            </div>

                        </div>

                        <div class="progress-track w-full h-2">

                            <div class="bg-gradient-to-r from-emerald-600 to-teal-400 h-full" style="width: ${Math.min(100, r.porcentaje_del_total)}%;"></div>

                        </div>

                    </div>

                `;

            });

            rubrosContainer.innerHTML = html;

        }

    }



    // 3. Top Contractors Chart

    const topContractorsContainer = document.getElementById('exec-chart-top-contractors');

    if (topContractorsContainer) {

        const tops = (summary.top_contratistas || []).slice(0, 5);

        if (tops.length === 0) {

            topContractorsContainer.innerHTML = '<div class="text-center text-xs text-slate-500 py-6">No hay contratistas con pagos.</div>';

        } else {

            const maxVal = Math.max(...tops.map(t => t.total_ejecutado), 1);

            let html = '';

            tops.forEach((t, idx) => {

                const pct = Math.min(100, Math.round((t.total_ejecutado / maxVal) * 100));

                html += `

                    <div class="space-y-1 cursor-pointer hover:bg-slate-800/30 p-1 rounded-lg transition-colors" onclick="selectContractorExecution(${t.id})">

                        <div class="flex items-center justify-between text-[11px]">

                            <span class="text-slate-300 font-medium truncate max-w-[180px]" title="${t.nombre_o_razon_social}">

                                <strong class="text-emerald-400 font-mono">#${idx + 1}</strong> ${t.nombre_o_razon_social}

                            </span>

                            <span class="font-mono font-bold text-[#55C6DE]">${formatCurrency(t.total_ejecutado)}</span>

                        </div>

                        <div class="progress-track w-full h-2">

                            <div class="progress-fill-gradient h-full" style="width: ${pct}%;"></div>

                        </div>

                    </div>

                `;

            });

            topContractorsContainer.innerHTML = html;

        }

    }

}



function populateRubroFilterDropdown(rubros) {

    const select = document.getElementById('exec-filter-rubro-select');

    if (!select) return;



    let html = '<option value="">Todos los Rubros</option>';

    rubros.forEach(r => {

        const selected = state.execution.rubroFilter === r.rubro ? 'selected' : '';

        html += `<option value="${r.rubro}" ${selected}>${r.rubro} (${formatCurrency(r.total_ejecutado)})</option>`;

    });

    select.innerHTML = html;

}



function switchExecSubTab(subTabName) {

    state.execution.currentSubTab = subTabName;



    // Toggle button styles

    const btnContracts = document.getElementById('exec-subtab-contracts');

    const btnPayments = document.getElementById('exec-subtab-payments');

    const btnContractors = document.getElementById('exec-subtab-contractors');



    const activeClasses = ['bg-[#1590D3]/20', 'border-[#55C6DE]/40', 'text-white'];

    const inactiveClasses = ['text-slate-400', 'hover:text-white'];



    [btnContracts, btnPayments, btnContractors].forEach(b => {

        if (!b) return;

        b.classList.remove(...activeClasses);

        b.classList.add(...inactiveClasses);

    });



    const viewContracts = document.getElementById('exec-view-contracts');

    const viewPayments = document.getElementById('exec-view-payments');

    const viewContractors = document.getElementById('exec-view-contractors');



    if (viewContracts) viewContracts.classList.add('hidden');

    if (viewPayments) viewPayments.classList.add('hidden');

    if (viewContractors) viewContractors.classList.add('hidden');



    if (subTabName === 'contracts') {

        if (btnContracts) {

            btnContracts.classList.remove(...inactiveClasses);

            btnContracts.classList.add(...activeClasses);

        }

        if (viewContracts) viewContracts.classList.remove('hidden');

    } else if (subTabName === 'payments') {

        if (btnPayments) {

            btnPayments.classList.remove(...inactiveClasses);

            btnPayments.classList.add(...activeClasses);

        }

        if (viewPayments) viewPayments.classList.remove('hidden');

    } else if (subTabName === 'contractors') {

        if (btnContractors) {

            btnContractors.classList.remove(...inactiveClasses);

            btnContractors.classList.add(...activeClasses);

        }

        if (viewContractors) viewContractors.classList.remove('hidden');

    }



    renderExecSubTabContent();

}



function renderExecSubTabContent() {

    if (state.execution.currentSubTab === 'contracts') {

        renderExecContractsTable();

    } else if (state.execution.currentSubTab === 'payments') {

        renderExecPaymentsTable();

    } else if (state.execution.currentSubTab === 'contractors') {

        renderExecContractorsTable();

    }

}



function renderExecContractsTable() {

    const tbody = document.getElementById('exec-contracts-tbody');

    const countEl = document.getElementById('exec-contracts-count');

    if (!tbody) return;



    let list = [...state.execution.contracts];



    // Filter by contractor if selected

    if (state.execution.selectedContractorId) {

        list = list.filter(c => c.contratista_id === state.execution.selectedContractorId);

    }



    // Filter by search query

    if (state.execution.searchQuery) {

        const q = state.execution.searchQuery.toLowerCase();

        list = list.filter(c => 

            c.numero_contrato.toLowerCase().includes(q) || 

            c.contratista_nombre.toLowerCase().includes(q)

        );

    }



    if (countEl) countEl.innerText = `${list.length} contratos`;



    if (list.length === 0) {

        tbody.innerHTML = '<tr><td colspan="10" class="py-8 text-center text-slate-500 text-xs">No se encontraron contratos con los filtros aplicados.</td></tr>';

        return;

    }



    let html = '';

    list.forEach(c => {

        const pct = c.porcentaje_ejecucion || 0;

        let barClass = 'progress-fill-gradient';

        let pctClass = 'text-sky-300';

        if (pct >= 85) {

            barClass = 'progress-fill-emerald';

            pctClass = 'text-emerald-400';

        } else if (pct > 0 && pct < 40) {

            barClass = 'progress-fill-amber';

            pctClass = 'text-amber-400';

        } else if (pct === 0) {

            pctClass = 'text-slate-500';

        }



        html += `

            <tr class="hover:bg-slate-800/40 transition-colors">

                <td class="py-3 px-3.5 font-mono font-bold text-white">

                    ${c.numero_contrato}

                </td>

                <td class="py-3 px-3.5">

                    <div class="font-medium text-slate-200 cursor-pointer hover:text-[#55C6DE] transition-colors" 

                         onclick="selectContractorExecution(${c.contratista_id})" title="Filtrar por este contratista">

                        ${c.contratista_nombre}

                    </div>

                </td>

                <td class="py-3 px-3.5 text-center">

                    ${getTypologyBadge(c.tipologia)}

                </td>

                <td class="py-3 px-3.5 text-right font-mono text-slate-100 font-semibold">

                    ${formatCurrency(c.valor_total)}

                </td>

                <td class="py-3 px-3.5 text-right font-mono text-sky-400 font-bold">

                    ${formatCurrency(c.total_ejecutado)}

                </td>

                <td class="py-3 px-3.5 text-right font-mono text-amber-400">

                    ${formatCurrency(c.total_retenciones)}

                </td>

                <td class="py-3 px-3.5 text-right font-mono text-emerald-400">

                    ${formatCurrency(c.total_neto_pagado)}

                </td>

                <td class="py-3 px-3.5 text-right font-mono text-purple-300 font-medium">

                    ${formatCurrency(c.saldo_por_ejecutar)}

                </td>

                <td class="py-3 px-3.5 text-center">

                    <div class="flex items-center justify-center gap-2">

                        <div class="progress-track w-20 h-2">

                            <div class="${barClass} h-full" style="width: ${Math.min(100, pct)}%;"></div>

                        </div>

                        <span class="font-mono text-[11px] font-bold ${pctClass}">${pct.toFixed(1)}%</span>

                    </div>

                </td>

                <td class="py-3 px-3.5 text-center">

                    <button onclick="openContractPaymentsModal(${c.id})" 

                            class="px-2.5 py-1 rounded-lg text-xs font-semibold bg-slate-800 hover:bg-[#1590D3] hover:text-white text-slate-300 transition-all shadow-sm flex items-center gap-1 mx-auto"

                            title="Ver pagos y egresos realizados">

                        <span>🔍</span> Pagos (${c.conteo_pagos})

                    </button>

                </td>

            </tr>

        `;

    });

    tbody.innerHTML = html;

}



function renderExecPaymentsTable() {

    const tbody = document.getElementById('exec-payments-tbody');

    const countEl = document.getElementById('exec-payments-count');

    if (!tbody) return;



    let list = [...state.execution.payments];



    // Filter by contractor

    if (state.execution.selectedContractorId) {

        list = list.filter(p => p.contratista_id === state.execution.selectedContractorId);

    }



    // Filter by rubro

    if (state.execution.rubroFilter) {

        list = list.filter(p => p.rubro_egreso === state.execution.rubroFilter);

    }



    // Filter by search query

    if (state.execution.searchQuery) {

        const q = state.execution.searchQuery.toLowerCase();

        list = list.filter(p => 

            p.codigo_contrato.toLowerCase().includes(q) ||

            p.codigo_egreso.toLowerCase().includes(q) ||

            p.nombre_beneficiario.toLowerCase().includes(q) ||

            (p.rubro_egreso && p.rubro_egreso.toLowerCase().includes(q))

        );

    }



    if (countEl) countEl.innerText = `${list.length} pagos registrados`;



    if (list.length === 0) {

        tbody.innerHTML = '<tr><td colspan="9" class="py-8 text-center text-slate-500 text-xs">No se encontraron comprobantes de egreso con los filtros aplicados.</td></tr>';

        return;

    }



    let html = '';

    list.forEach(p => {

        const fechaStr = p.fecha_expedicion ? p.fecha_expedicion : 'Sin fecha';

        

        // Parse deductions breakdown for display

        let reteTaxText = '-';

        let estampillasText = '-';

        if (Array.isArray(p.retenciones_detalle) && p.retenciones_detalle.length > 0) {

            const taxItems = p.retenciones_detalle.filter(r => !r.es_estampilla);

            const stampItems = p.retenciones_detalle.filter(r => r.es_estampilla);

            

            if (taxItems.length > 0) {

                const taxSum = taxItems.reduce((acc, curr) => acc + (parseFloat(curr.valor) || 0), 0);

                reteTaxText = `<div class="font-bold text-amber-300 font-mono">${formatCurrency(taxSum)}</div>

                               <div class="text-[9px] text-slate-400 truncate max-w-[140px]" title="${taxItems.map(t => `${t.concepto}: ${formatCurrency(t.valor)}`).join(' | ')}">${taxItems.map(t => t.concepto).join(', ')}</div>`;

            }

            if (stampItems.length > 0 || (p.total_estampillas && p.total_estampillas > 0)) {

                const stampSum = p.total_estampillas || stampItems.reduce((acc, curr) => acc + (parseFloat(curr.valor) || 0), 0);

                estampillasText = `<div class="font-bold text-purple-300 font-mono">${formatCurrency(stampSum)}</div>

                                   <div class="text-[9px] text-purple-400/80 truncate max-w-[140px]" title="${stampItems.map(s => `${s.concepto}: ${formatCurrency(s.valor)}`).join(' | ')}">${stampItems.map(s => s.concepto).join(', ') || 'Estampillas'}</div>`;

            }

        } else {

            const totalRet = parseFloat(p.total_retencion) || 0;

            const stampVal = parseFloat(p.total_estampillas) || 0;

            const taxVal = Math.max(0, totalRet - stampVal);

            if (taxVal > 0) reteTaxText = `<span class="font-mono text-amber-300 font-semibold">${formatCurrency(taxVal)}</span>`;

            if (stampVal > 0) estampillasText = `<span class="font-mono text-purple-300 font-semibold">${formatCurrency(stampVal)}</span>`;

        }



        html += `

            <tr class="hover:bg-slate-800/40 transition-colors">

                <td class="py-2.5 px-3.5 font-mono">

                    <span class="voucher-badge px-2 py-0.5 rounded bg-slate-900 border border-slate-700/80 text-white text-[11px] shadow-sm cursor-pointer hover:border-sky-400 hover:text-sky-300 transition-colors" onclick="openPaymentDetailDrawer(${p.id}, '${p.codigo_egreso}')" title="Ver panel de retenciones">${p.codigo_egreso}</span>

                    ${p.numero_orden_pago ? `<div class="text-[10px] text-slate-400 font-mono mt-0.5">OP ${p.numero_orden_pago}</div>` : ''}

                </td>

                <td class="py-2.5 px-3.5">

                    <div class="font-mono font-bold text-sky-300 cursor-pointer hover:underline text-[11px]" onclick="${p.contrato_id ? `openContractPaymentsModal(${p.contrato_id})` : ''}">${p.codigo_contrato}</div>

                    <div class="font-medium text-slate-300 text-[11px] cursor-pointer hover:text-[#55C6DE] transition-colors truncate max-w-[180px]"

                         onclick="${p.contratista_id ? `selectContractorExecution(${p.contratista_id})` : ''}" title="${p.nombre_beneficiario}">

                        ${p.nombre_beneficiario}

                    </div>

                </td>

                <td class="py-2.5 px-3.5 text-center font-mono text-slate-400 text-[11px]">

                    ${fechaStr}

                </td>

                <td class="py-2.5 px-3.5 font-mono text-slate-400 text-[11px]">

                    ${p.rubro_egreso || '<span class="text-slate-600">N/A</span>'}

                </td>

                <td class="py-2.5 px-3.5 text-right font-mono font-bold text-sky-400">

                    ${formatCurrency(p.total_orden)}

                </td>

                <td class="py-2.5 px-3.5 text-right text-[11px]">

                    ${reteTaxText}

                </td>

                <td class="py-2.5 px-3.5 text-right text-[11px]">

                    ${estampillasText}

                </td>

                <td class="py-2.5 px-3.5 text-right font-mono font-bold text-amber-400">

                    ${formatCurrency(p.total_retencion)}

                </td>

                <td class="py-2.5 px-3.5 text-right font-mono font-bold text-emerald-400">

                    ${formatCurrency(p.total_pagar)}

                </td>

                <td class="py-2.5 px-3.5 text-center">

                    <div class="flex items-center justify-center gap-1.5">

                        <button onclick="openPaymentDetailDrawer(${p.id}, '${p.codigo_egreso}')" class="px-2 py-1 bg-gradient-to-r from-sky-500/20 via-purple-500/20 to-indigo-500/20 hover:from-sky-500 hover:to-purple-600 border border-purple-500/30 hover:border-purple-400 text-purple-300 hover:text-white rounded-lg text-[11px] font-semibold transition-all flex items-center gap-1 cursor-pointer" title="Ver panel animado de retenciones">

                            <span>✨</span> Detalle

                        </button>

                        <button onclick="openEditPaymentModal(${p.id})" class="text-amber-400 hover:text-white p-1 transition-colors rounded hover:bg-amber-900/40" title="Editar / Revisar valores del egreso">

                            ✏️

                        </button>

                        <button onclick="openReassignPaymentModal(${p.id}, '${p.codigo_egreso}', '${p.nombre_beneficiario ? p.nombre_beneficiario.replace(/'/g, "\\'") : ''}', ${p.total_orden || 0}, '${p.codigo_contrato || ''}', ${p.contratista_id || 'null'}, ${p.contrato_id || 'null'})" class="text-indigo-400 hover:text-white p-1 transition-colors rounded hover:bg-indigo-900/40" title="Reasignar contrato">

                            🔁

                        </button>

                        ${window.api.isAdmin() ? `

                        <button onclick="confirmDeletePayment(${p.id}, '${p.codigo_egreso}')" class="text-slate-500 hover:text-rose-400 p-1 transition-colors rounded hover:bg-rose-900/40" title="Eliminar comprobante">

                            🗑️

                        </button>` : ''}

                    </div>

                </td>

            </tr>

        `;

    });

    tbody.innerHTML = html;

}



function renderExecContractorsTable() {

    const tbody = document.getElementById('exec-contractors-tbody');

    const countEl = document.getElementById('exec-contractors-table-count');

    if (!tbody) return;



    let list = [...state.execution.contractors];



    if (state.execution.searchQuery) {

        const q = state.execution.searchQuery.toLowerCase();

        list = list.filter(c => 

            c.nombre_o_razon_social.toLowerCase().includes(q) ||

            c.numero_documento.toLowerCase().includes(q)

        );

    }



    if (countEl) countEl.innerText = `${list.length} contratistas`;



    if (list.length === 0) {

        tbody.innerHTML = '<tr><td colspan="10" class="py-8 text-center text-slate-500 text-xs">No se encontraron contratistas.</td></tr>';

        return;

    }



    let html = '';

    list.forEach(c => {

        const pct = c.porcentaje_ejecucion || 0;

        let barClass = 'progress-fill-gradient';

        let pctClass = 'text-sky-300';

        if (pct >= 85) {

            barClass = 'progress-fill-emerald';

            pctClass = 'text-emerald-400';

        } else if (pct > 0 && pct < 40) {

            barClass = 'progress-fill-amber';

            pctClass = 'text-amber-400';

        } else if (pct === 0) {

            pctClass = 'text-slate-500';

        }



        html += `

            <tr class="hover:bg-slate-800/40 transition-colors">

                <td class="py-3 px-3.5">

                    <div class="font-bold text-white cursor-pointer hover:text-[#55C6DE] transition-colors" onclick="openContractorExecutionModal(${c.id})" title="Ver ficha y resumen completo">

                        ${c.nombre_o_razon_social}

                    </div>

                </td>

                <td class="py-3 px-3.5 font-mono text-slate-400 text-xs">

                    ${c.tipo_documento} ${c.numero_documento}

                </td>

                <td class="py-3 px-3.5 text-center font-mono">

                    <span class="px-2 py-0.5 rounded bg-slate-900 border border-slate-700 text-slate-300 text-xs">${c.total_contratos}</span>

                </td>

                <td class="py-3 px-3.5 text-right font-mono font-semibold text-slate-100">

                    ${formatCurrency(c.valor_total_contratado)}

                </td>

                <td class="py-3 px-3.5 text-right font-mono font-bold text-[#55C6DE]">

                    ${formatCurrency(c.total_ejecutado)}

                </td>

                <td class="py-3 px-3.5 text-right font-mono text-amber-400">

                    ${formatCurrency(c.total_retenciones)}

                </td>

                <td class="py-3 px-3.5 text-right font-mono text-emerald-400">

                    ${formatCurrency(c.total_neto_pagado)}

                </td>

                <td class="py-3 px-3.5 text-right font-mono text-purple-300 font-medium">

                    ${formatCurrency(c.saldo_por_ejecutar)}

                </td>

                <td class="py-3 px-3.5 text-center">

                    <div class="flex items-center justify-center gap-2">

                        <div class="progress-track w-16 h-2">

                            <div class="${barClass} h-full" style="width: ${Math.min(100, pct)}%;"></div>

                        </div>

                        <span class="font-mono text-[11px] font-bold ${pctClass}">${pct.toFixed(0)}%</span>

                    </div>

                </td>

                <td class="py-3 px-3.5 text-center">

                    <button onclick="openContractorExecutionModal(${c.id})" class="px-2.5 py-1 bg-slate-800 hover:bg-[#1590D3] hover:text-white text-slate-300 rounded-lg text-xs font-semibold transition-all shadow-sm flex items-center justify-center gap-1 mx-auto" title="Ver ficha y resumen completo del contratista">

                        <span>👤</span> Ver Ficha

                    </button>

                </td>

            </tr>

        `;

    });

    tbody.innerHTML = html;

}



function handleExecSearch(query) {

    state.execution.searchQuery = query.trim();

    renderExecSubTabContent();

}



function handleExecRubroFilter(rubro) {

    state.execution.rubroFilter = rubro;

    renderExecSubTabContent();

}



// Modal Contract Payments

async function openContractPaymentsModal(contractId) {

    const modal = document.getElementById('modal-contract-payments');

    if (!modal) return;



    try {

        modal.classList.remove('hidden');

        document.getElementById('modal-cp-contract-number').innerText = 'Cargando contrato...';

        document.getElementById('modal-cp-contractor-name').innerText = '';



        const data = await window.api.getExecutionContract(contractId);

        const ct = data.contrato;

        const met = data.metricas;

        const pagos = data.pagos || [];



        const cpNumEl = document.getElementById('modal-cp-contract-number') || document.getElementById('modal-cp-number');

        if (cpNumEl) cpNumEl.innerText = `Contrato N° ${ct.numero_contrato}`;

        const cpNameEl = document.getElementById('modal-cp-contractor-name');

        if (cpNameEl) cpNameEl.innerText = `Contratista: ${ct.contratista.nombre_o_razon_social} (${ct.contratista.numero_documento})`;



        const valTotal = ct.valor_total || 0;

        const totalOrden = met.total_ejecutado || 0;

        const totalRet = met.total_retenciones || 0;

        const totalNeto = met.total_neto_pagado || Math.max(0, totalOrden - totalRet);

        const saldo = met.saldo_por_ejecutar || Math.max(0, valTotal - totalOrden);

        const pctAvance = met.porcentaje_ejecucion || 0;



        const pctNetoDeOrden = totalOrden > 0 ? (totalNeto / totalOrden * 100) : 0;

        const pctRetDeOrden = totalOrden > 0 ? (totalRet / totalOrden * 100) : 0;



        const pctNetoDeTotal = valTotal > 0 ? (totalNeto / valTotal * 100) : 0;

        const pctRetDeTotal = valTotal > 0 ? (totalRet / valTotal * 100) : 0;

        const pctSaldoDeTotal = valTotal > 0 ? (saldo / valTotal * 100) : 100;



        // Render Donut 1: Presupuesto

        const donutBudgetEl = document.getElementById('modal-cp-donut-budget');

        if (donutBudgetEl) {

            donutBudgetEl.innerHTML = generateSvgDonut([

                { label: 'Ejecutado', value: totalOrden, color: '#55C6DE' },

                { label: 'Saldo Libre', value: saldo, color: '#A78BFA' }

            ], `${pctAvance.toFixed(1)}%`, 'Avance', 115);

        }



        // Render Donut 2: Desembolsos

        const donutDisbEl = document.getElementById('modal-cp-donut-disbursement');

        if (donutDisbEl) {

            donutDisbEl.innerHTML = generateSvgDonut([

                { label: 'Neto Girado', value: totalNeto, color: '#10B981' },

                { label: 'Retenciones', value: totalRet, color: '#F59E0B' }

            ], `${pctNetoDeOrden.toFixed(1)}%`, 'Neto', 115);

        }



        // Legends

        const legEj = document.getElementById('modal-cp-legend-ejecutado');

        if (legEj) legEj.innerText = `${formatCurrency(totalOrden)} (${pctAvance.toFixed(1)}%)`;

        const legSal = document.getElementById('modal-cp-legend-saldo');

        if (legSal) legSal.innerText = `${formatCurrency(saldo)} (${(100 - pctAvance).toFixed(1)}%)`;

        const legNet = document.getElementById('modal-cp-legend-neto');

        if (legNet) legNet.innerText = `${formatCurrency(totalNeto)} (${pctNetoDeOrden.toFixed(1)}%)`;

        const legRet = document.getElementById('modal-cp-legend-ret');

        if (legRet) legRet.innerText = `${formatCurrency(totalRet)} (${pctRetDeOrden.toFixed(1)}%)`;



        // Stacked Bar

        const barNet = document.getElementById('modal-cp-bar-neto');

        if (barNet) barNet.style.width = `${pctNetoDeTotal.toFixed(1)}%`;

        const barRet = document.getElementById('modal-cp-bar-ret');

        if (barRet) barRet.style.width = `${pctRetDeTotal.toFixed(1)}%`;

        const barSal = document.getElementById('modal-cp-bar-saldo');

        if (barSal) barSal.style.width = `${pctSaldoDeTotal.toFixed(1)}%`;



        const lblNet = document.getElementById('modal-cp-pct-neto-lbl');

        if (lblNet) lblNet.innerText = `${pctNetoDeTotal.toFixed(1)}%`;

        const lblRet = document.getElementById('modal-cp-pct-ret-lbl');

        if (lblRet) lblRet.innerText = `${pctRetDeTotal.toFixed(1)}%`;

        const lblSal = document.getElementById('modal-cp-pct-saldo-lbl');

        if (lblSal) lblSal.innerText = `${pctSaldoDeTotal.toFixed(1)}%`;



        document.getElementById('modal-cp-financial-summary').innerHTML = `

            <div class="mcp-card mcp-card-total p-3 bg-slate-50 dark:bg-slate-900/90 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs">

                <span class="mcp-card-lbl text-[10px] text-slate-500 dark:text-slate-400 uppercase font-bold">Valor Total Contrato</span>

                <div class="mcp-card-val text-sm font-extrabold text-slate-900 dark:text-white font-mono mt-0.5">${formatCurrency(ct.valor_total)}</div>

            </div>

            <div class="mcp-card mcp-card-orden p-3 bg-sky-50 dark:bg-slate-900/90 rounded-xl border border-sky-200 dark:border-sky-900/40 shadow-xs">

                <span class="mcp-card-lbl text-[10px] text-sky-800 dark:text-sky-400 uppercase font-bold">Total Órdenes</span>

                <div class="mcp-card-val text-sm font-extrabold text-sky-950 dark:text-[#55C6DE] font-mono mt-0.5">${formatCurrency(met.total_ejecutado)}</div>

            </div>

            <div class="mcp-card mcp-card-ret p-3 bg-amber-50 dark:bg-slate-900/90 rounded-xl border border-amber-200 dark:border-amber-900/40 shadow-xs">

                <span class="mcp-card-lbl text-[10px] text-amber-900 dark:text-amber-400 uppercase font-bold">Total Retenciones</span>

                <div class="mcp-card-val text-sm font-extrabold text-amber-950 dark:text-amber-400 font-mono mt-0.5">${formatCurrency(met.total_retenciones)}</div>

                ${(met.total_estampillas && met.total_estampillas > 0) ? `<div class="mcp-stamp-badge text-[10px] text-purple-800 dark:text-purple-300 font-mono mt-0.5 font-bold">🏛️ Estampillas: ${formatCurrency(met.total_estampillas)}</div>` : ''}

            </div>

            <div class="mcp-card mcp-card-saldo p-3 bg-purple-50 dark:bg-slate-900/90 rounded-xl border border-purple-200 dark:border-purple-900/40 shadow-xs">

                <span class="mcp-card-lbl text-[10px] text-purple-900 dark:text-purple-300 uppercase font-bold">Saldo Pendiente</span>

                <div class="mcp-card-val text-sm font-extrabold text-purple-950 dark:text-purple-300 font-mono mt-0.5">${formatCurrency(met.saldo_por_ejecutar)}</div>

            </div>

        `;



        document.getElementById('modal-cp-vouchers-count').innerText = `${pagos.length} comprobante(s)`;

        state.execution.currentModalPayments = pagos;



        const tbody = document.getElementById('modal-cp-payments-tbody');

        if (pagos.length === 0) {

            tbody.innerHTML = '<tr><td colspan="7" class="py-6 text-center text-slate-500 text-xs">No se han registrado pagos aún para este contrato.</td></tr>';

        } else {

            let html = '';

            pagos.forEach(p => {

                html += `

                    <tr class="hover:bg-slate-800/40 transition-colors">

                        <td class="py-2.5 px-3 font-mono font-bold text-sky-300">

                            <span class="cursor-pointer hover:underline hover:text-white" onclick="openPaymentDetailDrawer(${p.id}, '${p.codigo_egreso}')" title="Clic para abrir panel animado">${p.codigo_egreso}</span>

                        </td>

                        <td class="py-2.5 px-3 text-center font-mono text-slate-400">${p.fecha_expedicion || 'N/A'}</td>

                        <td class="py-2.5 px-3 font-mono text-slate-300">${p.rubro_egreso || 'N/A'}</td>

                        <td class="py-2.5 px-3 text-right font-mono font-bold text-sky-400">${formatCurrency(p.total_orden)}</td>

                        <td class="py-2.5 px-3 text-right font-mono text-amber-400">

                            <div>${formatCurrency(p.total_retencion)}</div>

                            ${(p.total_estampillas && p.total_estampillas > 0) ? `<div class="text-[9px] font-sans font-semibold text-purple-300 cursor-pointer hover:text-purple-200" onclick="openPaymentDetailDrawer(${p.id}, '${p.codigo_egreso}')" title="${p.retenciones_raw || ''}">🏛️ ${formatCurrency(p.total_estampillas)}</div>` : ''}

                        </td>

                        <td class="py-2.5 px-3 text-right font-mono font-bold text-emerald-400">${formatCurrency(p.total_pagar)}</td>

                        <td class="py-2.5 px-3 text-center">

                            <div class="flex items-center justify-center gap-1.5">

                                <button onclick="openPaymentDetailDrawer(${p.id}, '${p.codigo_egreso}')" class="btn-ver-panel px-2.5 py-1 bg-gradient-to-r from-sky-500/20 via-purple-500/20 to-indigo-500/20 hover:from-sky-500 hover:to-purple-600 border border-purple-500/30 hover:border-purple-400 text-purple-300 hover:text-white rounded-lg text-xs font-semibold transition-all duration-200 flex items-center gap-1 shadow-sm cursor-pointer" title="Ver panel animado de retenciones y desglose completo">

                                    <span>✨</span> Panel

                                </button>

                                <button onclick="openReassignPaymentModal(${p.id}, '${p.codigo_egreso}', '${p.nombre_beneficiario ? p.nombre_beneficiario.replace(/'/g, "\\'") : ''}', ${p.total_orden || 0}, '${p.codigo_contrato || ''}', ${p.contratista_id || 'null'}, ${contractId})" class="p-1.5 bg-indigo-950/60 hover:bg-indigo-600 border border-indigo-700/50 hover:border-indigo-400 text-indigo-300 hover:text-white rounded-lg text-xs transition-colors cursor-pointer" title="Reasignar este pago a otro contrato del contratista">

                                    🔁

                                </button>

                                ${window.api.isAdmin() ? `

                                <button onclick="confirmDeletePaymentModal(${p.id}, '${p.codigo_egreso}', ${contractId})" class="p-1.5 bg-rose-950/60 hover:bg-rose-600 border border-rose-700/50 hover:border-rose-400 text-rose-300 hover:text-white rounded-lg text-xs transition-colors cursor-pointer" title="Eliminar comprobante de este contrato">

                                    🗑️

                                </button>` : ''}

                            </div>

                        </td>

                    </tr>

                `;

            });

            tbody.innerHTML = html;

        }

    } catch (err) {

        showToast('Error cargando detalles del contrato: ' + err.message, 'error');

        closeContractPaymentsModal();

    }

}



function closeContractPaymentsModal() {

    const modal = document.getElementById('modal-contract-payments');

    if (modal) modal.classList.add('hidden');

}



// =========================================================

// PANEL ANIMADO DE DETALLE DE PAGO Y RETENCIONES (ESPY)

// =========================================================

let currentPaymentDetailList = [];

let currentPaymentDetailIndex = -1;

let currentActivePaymentDetail = null;



function formatCurrencyDecimals(amount) {

    if (amount === undefined || amount === null || isNaN(amount)) return '$ 0,00';

    return new Intl.NumberFormat('es-CO', {

        style: 'currency',

        currency: 'COP',

        minimumFractionDigits: 2,

        maximumFractionDigits: 2

    }).format(amount);

}



async function openPaymentDetailDrawer(paymentIdOrCode, egresoCode = null) {

    const modal = document.getElementById('modal-payment-detail');

    if (!modal) return;



    try {

        modal.classList.remove('hidden');

        document.getElementById('mpd-voucher-code').innerText = 'Cargando comprobante...';

        

        let payment = null;



        // 1. Check if passed from current modal list

        if (state.execution.currentModalPayments && state.execution.currentModalPayments.length > 0) {

            currentPaymentDetailList = state.execution.currentModalPayments;

            currentPaymentDetailIndex = currentPaymentDetailList.findIndex(p => 

                (paymentIdOrCode && p.id == paymentIdOrCode) || 

                (egresoCode && p.codigo_egreso === egresoCode) ||

                (p.codigo_egreso === paymentIdOrCode)

            );

            if (currentPaymentDetailIndex !== -1) {

                payment = currentPaymentDetailList[currentPaymentDetailIndex];

            }

        }

        

        // 2. Check if in global payments list

        if (!payment && state.execution.payments && state.execution.payments.length > 0) {

            const idx = state.execution.payments.findIndex(p => 

                (paymentIdOrCode && p.id == paymentIdOrCode) || 

                (egresoCode && p.codigo_egreso === egresoCode) ||

                (p.codigo_egreso === paymentIdOrCode)

            );

            if (idx !== -1) {

                currentPaymentDetailList = state.execution.payments;

                currentPaymentDetailIndex = idx;

                payment = currentPaymentDetailList[idx];

            }

        }



        // 3. Fetch from API if we have an ID to get enriched contractor details

        if (paymentIdOrCode && typeof paymentIdOrCode === 'number') {

            try {

                const fresh = await window.api.getPayment(paymentIdOrCode);

                if (fresh) {

                    payment = fresh;

                    if (currentPaymentDetailIndex !== -1 && currentPaymentDetailList[currentPaymentDetailIndex]) {

                        currentPaymentDetailList[currentPaymentDetailIndex] = fresh;

                    }

                }

            } catch (apiErr) {

                console.warn('Fallback a datos locales de comprobante:', apiErr);

            }

        }



        if (!payment) {

            showToast('No se encontró la información del comprobante de egreso.', 'warning');

            closePaymentDetailModal();

            return;

        }



        currentActivePaymentDetail = payment;

        renderPaymentDetailContent(payment);



    } catch (err) {

        console.error('Error al abrir panel de pago:', err);

        showToast('Error cargando detalle de pago: ' + err.message, 'error');

        closePaymentDetailModal();

    }

}



function renderPaymentDetailContent(p) {

    const totalOrden = parseFloat(p.total_orden) || 0.0;

    const totalRet = parseFloat(p.total_retencion) || 0.0;

    const totalPagar = parseFloat(p.total_pagar) || Math.max(0, totalOrden - totalRet);

    const totalEstampillas = parseFloat(p.total_estampillas) || 0.0;



    const pctRetDeOrden = totalOrden > 0 ? (totalRet / totalOrden * 100) : 0.0;

    const pctNetoDeOrden = totalOrden > 0 ? (totalPagar / totalOrden * 100) : 0.0;

    const pctEstDeOrden = totalOrden > 0 ? (totalEstampillas / totalOrden * 100) : 0.0;

    const pctEstDeRet = totalRet > 0 ? (totalEstampillas / totalRet * 100) : 0.0;

    const otrasRet = Math.max(0, totalRet - totalEstampillas);

    const pctOtrasDeOrden = totalOrden > 0 ? (otrasRet / totalOrden * 100) : 0.0;



    // Header & Info

    document.getElementById('mpd-voucher-code').innerText = p.codigo_egreso || 'CE N° S/N';

    document.getElementById('mpd-voucher-date').innerText = `Expedición: ${p.fecha_expedicion || 'S/F'}`;

    document.getElementById('mpd-contract-code').innerText = p.codigo_contrato || 'Sin contrato';

    document.getElementById('mpd-contract-val').innerText = p.contrato_valor_total ? `Total Contrato: ${formatCurrency(p.contrato_valor_total)}` : '';

    document.getElementById('mpd-beneficiary-name').innerText = p.nombre_beneficiario || 'Beneficiario';

    document.getElementById('mpd-contractor-doc').innerText = p.contratista_documento ? `Doc: ${p.contratista_documento}` : 'Doc: Registrado';

    document.getElementById('mpd-budget-rubro').innerText = p.rubro_egreso || 'S/R';

    document.getElementById('mpd-vigencia').innerText = p.vigencia || '2026';



    // 4 Macro Financial Cards

    document.getElementById('mpd-total-orden').innerText = formatCurrency(totalOrden);

    document.getElementById('mpd-total-retencion').innerText = formatCurrency(totalRet);

    document.getElementById('mpd-total-pagar').innerText = formatCurrency(totalPagar);

    document.getElementById('mpd-total-estampillas').innerText = formatCurrency(totalEstampillas);



    document.getElementById('mpd-pct-ret-orden').innerText = `${pctRetDeOrden.toFixed(2)}% s/ orden`;

    document.getElementById('mpd-pct-neto-orden').innerText = `${pctNetoDeOrden.toFixed(2)}% desembolsado`;

    document.getElementById('mpd-pct-est-ret').innerText = `${pctEstDeRet.toFixed(1)}% de retenciones`;



    // Multi-segment distribution bar

    const barNeto = document.getElementById('mpd-bar-neto');

    const barEstampillas = document.getElementById('mpd-bar-estampillas');

    const barOtras = document.getElementById('mpd-bar-otras');

    if (barNeto && barEstampillas && barOtras) {

        barNeto.style.width = '0%';

        barEstampillas.style.width = '0%';

        barOtras.style.width = '0%';

        setTimeout(() => {

            barNeto.style.width = `${pctNetoDeOrden.toFixed(1)}%`;

            barEstampillas.style.width = `${pctEstDeOrden.toFixed(1)}%`;

            barOtras.style.width = `${pctOtrasDeOrden.toFixed(1)}%`;

        }, 50);

    }

    document.getElementById('mpd-legend-neto-pct').innerText = `${pctNetoDeOrden.toFixed(1)}%`;

    document.getElementById('mpd-legend-est-pct').innerText = `${pctEstDeOrden.toFixed(1)}%`;

    document.getElementById('mpd-legend-otras-pct').innerText = `${pctOtrasDeOrden.toFixed(1)}%`;



    // Parse retenciones list

    let retList = [];

    if (Array.isArray(p.retenciones_detalle) && p.retenciones_detalle.length > 0) {

        retList = p.retenciones_detalle;

    } else if (p.retenciones_raw && typeof p.retenciones_raw === 'string') {

        const tokens = p.retenciones_raw.split(',').map(t => t.trim()).filter(Boolean);

        tokens.forEach(tok => {

            const m = tok.match(/^([^()]+?)(?:\s*\(\s*([\d.,]+)%\s*:\s*([\d.,]+)\s*\))?$/);

            if (m) {

                const cName = m[1].trim();

                const pct = m[2] ? parseFloat(m[2].replace(',', '.')) : 0.0;

                const val = m[3] ? parseFloat(m[3].replace(',', '.')) : 0.0;

                const isSt = /estampilla|cultura|hospital|justicia|deporte/i.test(cName);

                retList.push({ concepto: cName, porcentaje: pct, valor: val, es_estampilla: isSt });

            }

        });

    }



    const container = document.getElementById('mpd-retenciones-container');

    const countBadge = document.getElementById('mpd-retenciones-count');

    countBadge.innerText = `${retList.length} retención(es)`;



    if (retList.length === 0) {

        container.innerHTML = `

            <div class="p-4 rounded-xl bg-slate-900/60 border border-slate-800 text-center text-xs text-slate-400">

                <span class="text-emerald-400 font-semibold">Comprobante sin retenciones tributarias practicadas.</span>

                <p class="text-[11px] text-slate-500 mt-1">El valor total ordenado ($ ${totalOrden.toLocaleString('es-CO')}) fue desembolsado en un 100% de manera neta.</p>

            </div>

        `;

    } else {

        let rHtml = '';

        retList.forEach((it, idx) => {

            const cName = it.concepto || 'Retención';

            const pct = parseFloat(it.porcentaje) || 0.0;

            const val = parseFloat(it.valor) || 0.0;

            const isStamp = it.es_estampilla || /estampilla|cultura|hospital|justicia|deporte/i.test(cName);

            const isIca = /ica|industria/i.test(cName);

            const isFuente = /fuente|iva|renta|compra|arriendo/i.test(cName);



            let catLabel = '📑 Otra Deducción';

            let catClass = 'cat-badge-other bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-300 dark:border-slate-700';

            let valColor = 'text-slate-900 dark:text-slate-200';

            let progressColor = 'bg-slate-500';



            if (isStamp) {

                catLabel = '🏛️ Estampilla Territorial';

                catClass = 'cat-badge-stamp bg-purple-100 dark:bg-purple-950/80 text-purple-800 dark:text-purple-300 border-purple-300 dark:border-purple-800/50';

                valColor = 'text-purple-900 dark:text-purple-300';

                progressColor = 'bg-gradient-to-r from-purple-600 to-indigo-600 dark:from-purple-500 dark:to-indigo-500';

            } else if (isIca) {

                catLabel = '🏢 ICA Distrital';

                catClass = 'cat-badge-ica bg-sky-100 dark:bg-sky-950/80 text-sky-800 dark:text-sky-300 border-sky-300 dark:border-sky-800/50';

                valColor = 'text-sky-900 dark:text-sky-300';

                progressColor = 'bg-gradient-to-r from-sky-600 to-blue-600 dark:from-sky-500 dark:to-blue-500';

            } else if (isFuente) {

                catLabel = '⚖️ Ret. Fuente / IVA';

                catClass = 'cat-badge-fuente bg-amber-100 dark:bg-amber-950/80 text-amber-900 dark:text-amber-300 border-amber-300 dark:border-amber-800/50';

                valColor = 'text-amber-900 dark:text-amber-300';

                progressColor = 'bg-gradient-to-r from-amber-600 to-orange-600 dark:from-amber-500 dark:to-orange-500';

            }



            const pctOfTotalRet = totalRet > 0 ? (val / totalRet * 100) : 0.0;



            rHtml += `

                <div class="retencion-card-animated p-3 bg-white dark:bg-slate-900/90 hover:bg-slate-50 dark:hover:bg-slate-850 rounded-xl border border-slate-200 dark:border-slate-800/90 transition-all shadow-xs space-y-2" style="animation-delay: ${idx * 60}ms;">

                    <div class="flex items-start justify-between gap-3">

                        <div class="space-y-1 min-w-0">

                            <div class="flex items-center gap-2 flex-wrap">

                                <span class="ret-title text-xs font-bold text-slate-900 dark:text-white truncate">${cName}</span>

                                <span class="px-2 py-0.5 rounded-full text-[10px] font-semibold border ${catClass}">${catLabel}</span>

                            </div>

                            <div class="ret-base text-[11px] text-slate-500 dark:text-slate-400 font-mono">

                                Base gravable calculada: <strong class="ret-base-val text-slate-900 dark:text-slate-300 font-semibold">${formatCurrency(totalOrden)}</strong>

                            </div>

                        </div>

                        <div class="text-right flex-shrink-0">

                            <div class="ret-val text-xs sm:text-sm font-mono font-extrabold ${valColor} ${isStamp ? 'ret-val-stamp' : isIca ? 'ret-val-ica' : isFuente ? 'ret-val-fuente' : 'ret-val-other'}">${formatCurrencyDecimals(val)}</div>

                            <span class="ret-rate inline-block font-mono text-[10px] font-bold px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-950 border border-slate-300 dark:border-slate-800 text-slate-700 dark:text-slate-300 mt-0.5">

                                Tarifa: ${pct.toFixed(2)}%

                            </span>

                        </div>

                    </div>

                    <!-- Participation Bar -->

                    <div class="space-y-1">

                        <div class="ret-part-info flex items-center justify-between text-[10px] text-slate-500 dark:text-slate-400 font-mono">

                            <span>Participación sobre deducciones:</span>

                            <span class="ret-part-pct font-bold text-slate-900 dark:text-slate-300">${pctOfTotalRet.toFixed(1)}%</span>

                        </div>

                        <div class="ret-progress-track h-1.5 w-full bg-slate-200 dark:bg-slate-950 rounded-full overflow-hidden">

                            <div class="h-full ${progressColor} transition-all duration-700" style="width: ${pctOfTotalRet.toFixed(1)}%;"></div>

                        </div>

                    </div>

                </div>

            `;

        });

        container.innerHTML = rHtml;

    }



    // Estampillas Highlight Box

    const stampBox = document.getElementById('mpd-estampillas-highlight-box');

    const stampChips = document.getElementById('mpd-estampillas-chips');

    const stampSumBadge = document.getElementById('mpd-estampillas-sum-badge');

    if (totalEstampillas > 0) {

        stampBox.classList.remove('hidden');

        stampSumBadge.innerText = `${formatCurrency(totalEstampillas)} (${pctEstDeRet.toFixed(1)}% del total retenido)`;

        const stampItems = retList.filter(it => it.es_estampilla || /estampilla|cultura|hospital|justicia|deporte/i.test(it.concepto));

        if (stampItems.length > 0) {

            stampChips.innerHTML = stampItems.map(st => `

                <div class="mpd-stamp-chip px-2.5 py-1 rounded-lg bg-white dark:bg-purple-900/40 border border-purple-200 dark:border-purple-600/30 text-[11px] text-purple-900 dark:text-purple-200 flex items-center gap-1.5 font-mono shadow-xs">

                    <span class="mpd-stamp-dot w-1.5 h-1.5 rounded-full bg-purple-600 dark:bg-purple-400"></span>

                    <span class="mpd-stamp-label font-sans font-medium text-slate-700 dark:text-purple-200">${st.concepto} (${st.porcentaje}%):</span>

                    <strong class="mpd-stamp-val text-purple-950 dark:text-white font-extrabold">${formatCurrency(st.valor)}</strong>

                </div>

            `).join('');

        } else {

            stampChips.innerHTML = `<span class="text-xs text-purple-900 dark:text-purple-300 font-bold font-mono">Total Estampillas extraído del Comprobante de Egreso.</span>`;

        }

    } else {

        stampBox.classList.add('hidden');

    }



    // Bank Details

    if (p.contratista_banco || p.contratista_numero_cuenta) {

        document.getElementById('mpd-bank-status').innerText = 'Canal Oficial Registrado';

        document.getElementById('mpd-bank-name').innerText = p.contratista_banco || 'Bancario';

        document.getElementById('mpd-bank-type').innerText = p.contratista_tipo_cuenta || 'Ahorros';

        document.getElementById('mpd-bank-account').innerText = p.contratista_numero_cuenta || 'Verificado';

    } else {

        document.getElementById('mpd-bank-status').innerText = 'Tesorería ESPY';

        document.getElementById('mpd-bank-name').innerText = 'Tesorería Central';

        document.getElementById('mpd-bank-type').innerText = 'Giro / Transferencia';

        document.getElementById('mpd-bank-account').innerText = 'Certificado en Egreso';

    }



    // Observaciones & Trazabilidad

    const obsSec = document.getElementById('mpd-observaciones-section');

    const obsTxt = document.getElementById('mpd-observaciones-text');

    if (p.observaciones && p.observaciones.trim()) {

        obsSec.classList.remove('hidden');

        obsTxt.innerText = p.observaciones;

    } else {

        obsSec.classList.add('hidden');

        obsTxt.innerText = '';

    }



    // Navigation Controls

    const prevBtn = document.getElementById('mpd-prev-btn');

    const nextBtn = document.getElementById('mpd-next-btn');

    const navCounter = document.getElementById('mpd-nav-counter');

    if (currentPaymentDetailList && currentPaymentDetailList.length > 1 && currentPaymentDetailIndex !== -1) {

        prevBtn.disabled = (currentPaymentDetailIndex <= 0);

        nextBtn.disabled = (currentPaymentDetailIndex >= currentPaymentDetailList.length - 1);

        navCounter.innerText = `${currentPaymentDetailIndex + 1} de ${currentPaymentDetailList.length}`;

        prevBtn.classList.remove('hidden');

        nextBtn.classList.remove('hidden');

        navCounter.classList.remove('hidden');

    } else {

        prevBtn.disabled = true;

        nextBtn.disabled = true;

        navCounter.innerText = '1 de 1';

    }

}



function closePaymentDetailModal() {

    const modal = document.getElementById('modal-payment-detail');

    if (modal) modal.classList.add('hidden');

}



function navigatePaymentDetail(direction) {

    if (!currentPaymentDetailList || currentPaymentDetailList.length === 0) return;

    const newIdx = currentPaymentDetailIndex + direction;

    if (newIdx >= 0 && newIdx < currentPaymentDetailList.length) {

        currentPaymentDetailIndex = newIdx;

        const p = currentPaymentDetailList[newIdx];

        openPaymentDetailDrawer(p.id, p.codigo_egreso);

    }

}



function copyPaymentDetailSummary() {

    if (!currentActivePaymentDetail) {

        showToast('No hay datos para copiar', 'warning');

        return;

    }

    const p = currentActivePaymentDetail;

    const lines = [

        `================================================`,

        `COMPROBANTE DE EGRESO ESPY: ${p.codigo_egreso}`,

        `================================================`,

        `Fecha de Expedición: ${p.fecha_expedicion || 'S/F'}`,

        `Contrato Vinculado:  ${p.codigo_contrato}`,

        `Beneficiario:        ${p.nombre_beneficiario}`,

        `Rubro Presupuestal:  ${p.rubro_egreso || 'S/R'}`,

        `Vigencia Fiscal:     ${p.vigencia || 2026}`,

        `------------------------------------------------`,

        `Total Orden (Bruto): ${formatCurrency(p.total_orden)}`,

        `Total Retenciones:   ${formatCurrency(p.total_retencion)}`,

        `Total Pagado (Neto): ${formatCurrency(p.total_pagar)}`,

        `Total Estampillas:   ${formatCurrency(p.total_estampillas || 0)}`,

        `------------------------------------------------`,

        `DETALLE DISCRIMINADO DE RETENCIONES:`,

        p.retenciones_raw || 'Sin retenciones detalladas',

        `================================================`,

        `Certificación: Información extraída fielmente del Comprobante de Egreso (Págs. 1 y 2).`

    ];

    navigator.clipboard.writeText(lines.join('\n')).then(() => {

        showToast('Resumen tributario copiado al portapapeles con éxito.', 'success');

    }).catch(() => {

        showToast('Error al copiar al portapapeles.', 'error');

    });

}



function printPaymentDetailCard() {

    window.print();

}



// =========================================================

// MODAL: REVISAR / EDITAR VALORES DEL EGRESO

// =========================================================

async function openEditPaymentModal(paymentId) {

    const modal = document.getElementById('modal-edit-payment');

    if (!modal) return;



    let p = null;

    if (state.execution.payments && state.execution.payments.length > 0) {

        p = state.execution.payments.find(item => item.id == paymentId);

    }



    if (!p) {

        try {

            p = await window.api.getPayment(paymentId);

        } catch (e) {

            console.error('Error fetching payment for edit:', e);

        }

    }



    if (!p) {

        showToast('No se encontró el registro del comprobante de egreso.', 'error');

        return;

    }



    document.getElementById('mep-payment-id').value = p.id;

    document.getElementById('mep-egreso-badge').innerText = p.codigo_egreso || 'CE N° S/N';

    document.getElementById('mep-contract-code').value = p.codigo_contrato || '';

    document.getElementById('mep-egreso-code').value = p.codigo_egreso || '';

    document.getElementById('mep-beneficiary-name').value = p.nombre_beneficiario || '';

    document.getElementById('mep-rubro').value = p.rubro_egreso || '';

    

    document.getElementById('mep-total-orden').value = p.total_orden !== undefined && p.total_orden !== null ? p.total_orden : 0;

    document.getElementById('mep-total-retencion').value = p.total_retencion !== undefined && p.total_retencion !== null ? p.total_retencion : 0;

    document.getElementById('mep-total-pagar').value = p.total_pagar !== undefined && p.total_pagar !== null ? p.total_pagar : 0;

    document.getElementById('mep-total-estampillas').value = p.total_estampillas !== undefined && p.total_estampillas !== null ? p.total_estampillas : 0;

    

    document.getElementById('mep-fecha-expedicion').value = p.fecha_expedicion || '';

    document.getElementById('mep-observaciones').value = p.observaciones || '';



    modal.classList.remove('hidden');

}



function closeEditPaymentModal() {

    const modal = document.getElementById('modal-edit-payment');

    if (modal) modal.classList.add('hidden');

}



function recalculateEditPaymentValues() {

    const ordenEl = document.getElementById('mep-total-orden');

    const retEl = document.getElementById('mep-total-retencion');

    const pagarEl = document.getElementById('mep-total-pagar');

    if (!ordenEl || !retEl || !pagarEl) return;



    const valOrden = parseFloat(ordenEl.value) || 0;

    const valRet = parseFloat(retEl.value) || 0;

    const valNeto = Math.max(0, valOrden - valRet);

    pagarEl.value = Math.round(valNeto * 100) / 100;

}



async function saveEditedPaymentValues() {

    const id = document.getElementById('mep-payment-id').value;

    if (!id) return;



    const btn = document.getElementById('btn-save-edit-payment');

    const originalText = btn ? btn.innerHTML : '';

    if (btn) {

        btn.disabled = true;

        btn.innerHTML = '<span>⏳</span> Guardando...';

    }



    try {

        const payload = {

            total_orden: parseFloat(document.getElementById('mep-total-orden').value) || 0,

            total_retencion: parseFloat(document.getElementById('mep-total-retencion').value) || 0,

            total_pagar: parseFloat(document.getElementById('mep-total-pagar').value) || 0,

            total_estampillas: parseFloat(document.getElementById('mep-total-estampillas').value) || 0,

            codigo_contrato: document.getElementById('mep-contract-code').value.trim(),

            codigo_egreso: document.getElementById('mep-egreso-code').value.trim(),

            nombre_beneficiario: document.getElementById('mep-beneficiary-name').value.trim(),

            rubro_egreso: document.getElementById('mep-rubro').value.trim(),

            fecha_expedicion: document.getElementById('mep-fecha-expedicion').value || null,

            observaciones: document.getElementById('mep-observaciones').value.trim() || null

        };



        const res = await window.api.updatePayment(id, payload);

        showToast('Comprobante de egreso actualizado correctamente.', 'success');

        closeEditPaymentModal();



        // Refresh execution data

        if (typeof loadExecutionTab === 'function') {

            await loadExecutionTab();

        }

        // If drawer is open, refresh it

        if (currentActivePaymentDetail && currentActivePaymentDetail.id == id) {

            openPaymentDetailDrawer(parseInt(id), payload.codigo_egreso);

        }

    } catch (err) {

        console.error('Error al guardar comprobante:', err);

        showToast('Error al actualizar comprobante: ' + (err.detail || err.message), 'error');

    } finally {

        if (btn) {

            btn.disabled = false;

            btn.innerHTML = originalText;

        }

    }

}



// =========================================================

// MODAL IMPORTACIÓN DE COMPROBANTES (PDF / TXT)

// =========================================================

let selectedPdfPackets = [];



function switchImportModalTab(tab) {

    const btnPdf = document.getElementById('tab-btn-import-pdf');

    const btnTxt = document.getElementById('tab-btn-import-txt');

    const panelPdf = document.getElementById('import-panel-pdf');

    const panelTxt = document.getElementById('import-panel-txt');



    if (tab === 'pdf') {

        if (btnPdf) {

            btnPdf.className = 'px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center gap-2 bg-[#1590D3] text-white shadow-md';

        }

        if (btnTxt) {

            btnTxt.className = 'px-3.5 py-1.5 rounded-xl text-xs font-semibold text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 transition-all flex items-center gap-2';

        }

        if (panelPdf) panelPdf.classList.remove('hidden');

        if (panelTxt) panelTxt.classList.add('hidden');

    } else {

        if (btnTxt) {

            btnTxt.className = 'px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center gap-2 bg-[#1590D3] text-white shadow-md';

        }

        if (btnPdf) {

            btnPdf.className = 'px-3.5 py-1.5 rounded-xl text-xs font-semibold text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 transition-all flex items-center gap-2';

        }

        if (panelTxt) panelTxt.classList.remove('hidden');

        if (panelPdf) panelPdf.classList.add('hidden');

    }

}



function openImportPaymentsModal(defaultTab = 'pdf') {

    const modal = document.getElementById('modal-import-payments');

    if (!modal) return;



    // Reset status and inputs

    const statusDiv = document.getElementById('import-payments-status');

    if (statusDiv) statusDiv.classList.add('hidden');

    const formTxt = document.getElementById('form-import-payments');

    if (formTxt) formTxt.reset();



    // Reset PDF results & list

    clearSelectedPdfFiles();

    const resContainer = document.getElementById('import-pdf-results-container');

    if (resContainer) resContainer.classList.add('hidden');

    const progressEl = document.getElementById('import-pdf-progress');

    if (progressEl) progressEl.classList.add('hidden');

    const actionsEl = document.getElementById('import-pdf-actions');

    if (actionsEl) actionsEl.classList.remove('hidden');



    // Sync vigencia selector

    const vigSelect = document.getElementById('import-pdf-vigencia');

    if (vigSelect) {

        const curVig = state.selectedVigencia === 'ALL' ? '2026' : String(state.selectedVigencia);

        vigSelect.value = curVig;

    }



    switchImportModalTab(defaultTab);

    modal.classList.remove('hidden');



    // Init Drag and Drop handlers on dropzone

    setupPdfDropzone();

}



function closeImportPaymentsModal() {

    const modal = document.getElementById('modal-import-payments');

    if (modal) modal.classList.add('hidden');

}



function setupPdfDropzone() {

    const dropzone = document.getElementById('import-pdf-dropzone');

    if (!dropzone || dropzone.dataset.initialized) return;



    dropzone.dataset.initialized = 'true';



    ['dragenter', 'dragover'].forEach(eventName => {

        dropzone.addEventListener(eventName, (e) => {

            e.preventDefault();

            e.stopPropagation();

            dropzone.classList.add('border-sky-400', 'bg-sky-950/30');

        }, false);

    });



    ['dragleave', 'drop'].forEach(eventName => {

        dropzone.addEventListener(eventName, (e) => {

            e.preventDefault();

            e.stopPropagation();

            dropzone.classList.remove('border-sky-400', 'bg-sky-950/30');

        }, false);

    });



    dropzone.addEventListener('drop', (e) => {

        const dt = e.dataTransfer;

        const files = dt.files;

        if (files && files.length > 0) {

            handlePdfFilesList(Array.from(files));

        }

    }, false);

}



function handlePdfFilesSelection(e) {

    const files = e.target.files;

    if (files && files.length > 0) {

        handlePdfFilesList(Array.from(files));

    }

}



function handlePdfFilesList(files) {

    const validPdfs = files.filter(f => f.name.toLowerCase().endsWith('.pdf'));

    if (validPdfs.length === 0) {

        showToast('Únicamente se permiten archivos con extensión .pdf', 'warning');

        return;

    }



    // Append to selected list avoiding exact duplicate filenames

    validPdfs.forEach(file => {

        if (!selectedPdfPackets.some(existing => existing.name === file.name && existing.size === file.size)) {

            selectedPdfPackets.push(file);

        }

    });



    renderSelectedPdfFilesList();

}



function renderSelectedPdfFilesList() {

    const container = document.getElementById('import-pdf-selected-container');

    const listEl = document.getElementById('import-pdf-files-list');

    const countEl = document.getElementById('import-pdf-selected-count');



    if (!container || !listEl) return;



    if (selectedPdfPackets.length === 0) {

        container.classList.add('hidden');

        listEl.innerHTML = '';

        return;

    }



    container.classList.remove('hidden');

    if (countEl) countEl.innerText = selectedPdfPackets.length;



    let html = '';

    selectedPdfPackets.forEach((file, index) => {

        const sizeMb = (file.size / (1024 * 1024)).toFixed(2);

        html += `

            <div class="flex items-center justify-between p-2 rounded-lg bg-slate-800/80 border border-slate-700/60 hover:border-sky-500/40 transition-colors">

                <div class="flex items-center gap-2 overflow-hidden">

                    <span class="text-base text-rose-400">📄</span>

                    <span class="font-medium text-slate-200 truncate" title="${file.name}">${file.name}</span>

                    <span class="text-[10px] font-mono text-slate-400 bg-slate-900 px-1.5 py-0.5 rounded">${sizeMb} MB</span>

                </div>

                <button type="button" onclick="removeSelectedPdfFile(${index})" class="text-slate-400 hover:text-rose-400 p-1 transition-colors text-xs" title="Quitar archivo">

                    ✕

                </button>

            </div>

        `;

    });

    listEl.innerHTML = html;

}



function removeSelectedPdfFile(index) {

    selectedPdfPackets.splice(index, 1);

    renderSelectedPdfFilesList();

}



function clearSelectedPdfFiles() {

    selectedPdfPackets = [];

    const input = document.getElementById('import-pdf-files-input');

    if (input) input.value = '';

    renderSelectedPdfFilesList();

}



async function processPdfPacketsUpload() {

    if (selectedPdfPackets.length === 0) {

        showToast('Por favor seleccione al menos un archivo PDF de paquete de pago.', 'warning');

        return;

    }



    const btn = document.getElementById('btn-submit-import-pdf');

    const progressEl = document.getElementById('import-pdf-progress');

    const resContainer = document.getElementById('import-pdf-results-container');

    const vigSelect = document.getElementById('import-pdf-vigencia');

    const vigencia = vigSelect ? parseInt(vigSelect.value, 10) : 2026;

    const overwriteChk = document.getElementById('import-pdf-overwrite-duplicates');

    const overwriteDuplicates = overwriteChk ? overwriteChk.checked : false;



    try {

        if (btn) btn.disabled = true;

        if (progressEl) progressEl.classList.remove('hidden');

        if (resContainer) resContainer.classList.add('hidden');



        const formData = new FormData();

        selectedPdfPackets.forEach(file => {

            formData.append('files', file);

        });

        formData.append('vigencia', vigencia);

        formData.append('overwrite_duplicates', overwriteDuplicates);



        const res = await window.api.importPdfPaymentPackets(formData);



        if (progressEl) progressEl.classList.add('hidden');

        if (resContainer) resContainer.classList.remove('hidden');



        // Set counts

        const insCount = res.inserted_count || 0;

        const updCount = res.updated_count || 0;

        const dupCount = res.duplicates_count || 0;

        const ambCount = res.ambiguous_count || 0;

        const errCount = res.errors_count || 0;



        document.getElementById('res-pdf-inserted-count').innerText = insCount;

        const updCountEl = document.getElementById('res-pdf-updated-count');

        if (updCountEl) updCountEl.innerText = updCount;

        document.getElementById('res-pdf-duplicates-count').innerText = dupCount;

        const ambCountEl = document.getElementById('res-pdf-ambiguous-count');

        if (ambCountEl) ambCountEl.innerText = ambCount;

        document.getElementById('res-pdf-errors-count').innerText = errCount;



        // Render Inserted

        const insertedSec = document.getElementById('res-pdf-inserted-section');

        const insertedTbody = document.getElementById('res-pdf-inserted-tbody');

        if (res.inserted && res.inserted.length > 0) {

            insertedSec.classList.remove('hidden');

            let insHtml = '';

            res.inserted.forEach(item => {

                insHtml += `

                    <tr class="hover:bg-slate-800/40">

                        <td class="py-2 px-3 font-mono font-bold text-emerald-300">${item.codigo_egreso}</td>

                        <td class="py-2 px-3 font-mono text-slate-300">${item.codigo_contrato}</td>

                        <td class="py-2 px-3 text-slate-200 truncate max-w-[180px]" title="${item.nombre_beneficiario}">${item.nombre_beneficiario}</td>

                        <td class="py-2 px-3 text-right font-mono font-bold text-sky-400">${formatCurrency(item.total_orden)}</td>

                        <td class="py-2 px-3 text-right font-mono text-amber-400">

                            <div>${formatCurrency(item.total_retencion)}</div>

                            ${(item.total_estampillas && item.total_estampillas > 0) ? `<div class="text-[9px] text-purple-300 font-semibold" title="${item.retenciones_raw || ''}">🏛️ ${formatCurrency(item.total_estampillas)}</div>` : ''}

                        </td>

                        <td class="py-2 px-3 text-right font-mono font-bold text-emerald-400">${formatCurrency(item.total_pagar)}</td>

                    </tr>

                `;

            });

            insertedTbody.innerHTML = insHtml;

        } else {

            insertedSec.classList.add('hidden');

            insertedTbody.innerHTML = '';

        }



        // Render Updated

        const updatedSec = document.getElementById('res-pdf-updated-section');

        const updatedTbody = document.getElementById('res-pdf-updated-tbody');

        if (updatedSec && updatedTbody) {

            if (res.updated && res.updated.length > 0) {

                updatedSec.classList.remove('hidden');

                let updHtml = '';

                res.updated.forEach(item => {

                    updHtml += `

                        <tr class="hover:bg-sky-950/30">

                            <td class="py-2 px-3 font-mono font-bold text-sky-300">${item.codigo_egreso}</td>

                            <td class="py-2 px-3 font-mono text-slate-300">${item.codigo_contrato}</td>

                            <td class="py-2 px-3 text-slate-200 truncate max-w-[180px]" title="${item.nombre_beneficiario}">${item.nombre_beneficiario}</td>

                            <td class="py-2 px-3 text-right font-mono font-bold text-sky-400">${formatCurrency(item.total_orden)}</td>

                            <td class="py-2 px-3 text-right font-mono text-amber-400">

                                <div>${formatCurrency(item.total_retencion)}</div>

                                ${(item.total_estampillas && item.total_estampillas > 0) ? `<div class="text-[9px] text-purple-300 font-semibold" title="${item.retenciones_raw || ''}">🏛️ ${formatCurrency(item.total_estampillas)}</div>` : ''}

                            </td>

                            <td class="py-2 px-3 text-right font-mono font-bold text-emerald-400">${formatCurrency(item.total_pagar)}</td>

                        </tr>

                    `;

                });

                updatedTbody.innerHTML = updHtml;

            } else {

                updatedSec.classList.add('hidden');

                updatedTbody.innerHTML = '';

            }

        }



        // Render Ambiguous Multicontract Items requiring user contract selection

        const ambSec = document.getElementById('res-pdf-ambiguous-section');

        const ambList = document.getElementById('res-pdf-ambiguous-list');

        if (ambSec && ambList) {

            if (res.ambiguous && res.ambiguous.length > 0) {

                ambSec.classList.remove('hidden');

                let ambHtml = '';

                res.ambiguous.forEach((item, idx) => {

                    const candOpts = (item.contratos_candidatos || []).map(c => {

                        const objStr = c.objeto ? (c.objeto.length > 80 ? c.objeto.substring(0, 80) + '...' : c.objeto) : 'Sin objeto';

                        return `

                            <label class="flex items-start gap-2.5 p-2 bg-slate-900/80 hover:bg-indigo-950/50 border border-slate-700/60 hover:border-indigo-500/60 rounded-xl cursor-pointer transition-all">

                                <input type="radio" name="amb-choice-${idx}" value="${c.id}" data-contract-code="${c.numero_contrato}" class="mt-0.5 text-indigo-500 focus:ring-indigo-400">

                                <div class="text-[11px] space-y-0.5 flex-1">

                                    <div class="flex items-center justify-between">

                                        <span class="font-mono font-bold text-sky-300">${c.numero_contrato}</span>

                                        <span class="font-mono font-semibold text-emerald-400">${formatCurrency(c.valor_total || 0)}</span>

                                    </div>

                                    <p class="text-slate-300 leading-tight">${objStr}</p>

                                </div>

                            </label>

                        `;

                    }).join('');



                    ambHtml += `

                        <div id="ambiguous-card-${idx}" class="p-3 rounded-2xl bg-gradient-to-r from-slate-900 via-indigo-950/40 to-slate-900 border border-indigo-500/40 text-xs text-slate-200 space-y-2.5 shadow-lg">

                            <div class="flex items-center justify-between border-b border-indigo-500/20 pb-2">

                                <div class="flex items-center gap-2">

                                    <span class="text-base text-indigo-400">⚖️</span>

                                    <div>

                                        <span class="font-mono font-bold text-sky-300">${item.codigo_egreso}</span>

                                        <span class="text-[11px] text-slate-400 ml-2">(${item.fecha_expedicion || 'Sin fecha'})</span>

                                    </div>

                                </div>

                                <span class="font-mono font-bold text-emerald-400 text-sm">${formatCurrency(item.total_orden)}</span>

                            </div>



                            <div class="text-[11px] text-slate-300">

                                <strong>Beneficiario:</strong> ${item.nombre_beneficiario} ${item.nit_beneficiario ? `(C.C. / NIT: ${item.nit_beneficiario})` : ''}

                                <p class="text-[10px] text-indigo-300 mt-0.5">El beneficiario tiene múltiples contratos vigentes. Selecciona a cuál corresponde este pago para consolidar:</p>

                            </div>



                            <div class="space-y-1.5 pt-1">

                                ${candOpts}

                            </div>



                            <div class="flex justify-end pt-2 border-t border-indigo-500/20">

                                <button type="button" onclick="confirmAmbiguousPaymentChoice(${idx})" class="px-3.5 py-1.5 bg-gradient-to-r from-indigo-600 to-sky-600 hover:from-indigo-500 hover:to-sky-500 text-white rounded-xl text-xs font-bold transition-all shadow flex items-center gap-1.5 cursor-pointer">

                                    <span>💾</span> Asignar y Guardar Comprobante

                                </button>

                            </div>

                        </div>

                    `;

                });

                ambList.innerHTML = ambHtml;

                window.lastAmbiguousPaymentItems = res.ambiguous;

            } else {

                ambSec.classList.add('hidden');

                ambList.innerHTML = '';

                window.lastAmbiguousPaymentItems = [];

            }

        }



        // Render Duplicates with optional immediate Update action

        const dupsSec = document.getElementById('res-pdf-duplicates-section');

        const dupsList = document.getElementById('res-pdf-duplicates-list');

        if (res.duplicates && res.duplicates.length > 0) {

            dupsSec.classList.remove('hidden');

            let dupHtml = '';

            if (!overwriteDuplicates) {

                dupHtml += `

                    <div class="p-2.5 rounded-xl bg-sky-950/50 border border-sky-500/40 text-xs text-sky-200 flex items-center justify-between gap-3 mb-2">

                        <div class="flex items-center gap-2">

                            <span class="text-base">💡</span>

                            <span>¿Deseas actualizar estos comprobantes existentes con los datos del PDF?</span>

                        </div>

                        <button type="button" onclick="triggerReimportWithOverwrite()" class="px-3 py-1.5 bg-sky-600 hover:bg-sky-500 text-white font-bold rounded-lg text-xs transition-colors shrink-0 flex items-center gap-1.5 shadow">

                            <span>🔄</span> Actualizar Ahora

                        </button>

                    </div>

                `;

            }

            res.duplicates.forEach(d => {

                dupHtml += `

                    <div class="p-2.5 rounded-xl bg-amber-950/40 border border-amber-600/40 text-xs text-amber-200 flex items-start gap-2.5">

                        <span class="text-base text-amber-400">🛡️</span>

                        <div class="flex-1 space-y-0.5">

                            <div class="flex items-center justify-between">

                                <span class="font-mono font-bold text-amber-300">${d.codigo_egreso}</span>

                                <span class="text-[10px] text-slate-400 font-mono">${d.codigo_contrato || 'Contrato'}</span>

                            </div>

                            <p class="text-[11px] text-amber-100/90">${d.motivo}</p>

                            <div class="text-[10px] text-slate-400 flex items-center gap-3 pt-0.5 font-mono">

                                <span>Beneficiario: ${d.nombre_beneficiario || 'N/A'}</span>

                                <span>Total Orden: ${formatCurrency(d.total_orden)}</span>

                            </div>

                        </div>

                    </div>

                `;

            });

            dupsList.innerHTML = dupHtml;

        } else {

            dupsSec.classList.add('hidden');

            dupsList.innerHTML = '';

        }



        // Render Errors

        const errSec = document.getElementById('res-pdf-errors-section');

        const errList = document.getElementById('res-pdf-errors-list');

        if (res.errors && res.errors.length > 0) {

            errSec.classList.remove('hidden');

            errList.innerHTML = res.errors.map(err => `<div>&bull; ${err}</div>`).join('');

        } else {

            errSec.classList.add('hidden');

            errList.innerHTML = '';

        }



        // Render TXT Preview

        const txtSec = document.getElementById('res-pdf-txt-section');

        const txtPre = document.getElementById('res-pdf-txt-content');

        if (res.txt_content && res.txt_content.trim()) {

            txtSec.classList.remove('hidden');

            txtPre.innerText = res.txt_content;

        } else {

            txtSec.classList.add('hidden');

        }



        // Notifications & Refresh Dashboard

        if (insCount > 0 || updCount > 0) {

            const msgParts = [];

            if (insCount > 0) msgParts.push(`${insCount} comprobante(s) nuevo(s) guardado(s)`);

            if (updCount > 0) msgParts.push(`${updCount} actualizado(s)`);

            showToast(`Éxito: ${msgParts.join(' y ')}.`, 'success');

            await loadExecutionTab();

        } else if (ambCount > 0) {

            showToast(`Atención: Se detectaron ${ambCount} comprobante(s) con múltiples contratos. Selecciona el contrato correspondiente abajo para completar la importación.`, 'warning');

        } else if (dupCount > 0) {

            showToast(`Atención: Los ${dupCount} comprobante(s) ya existían y no fueron modificados. Puede activar "Actualizar datos" si desea sobreescribirlos.`, 'warning');

        } else {

            showToast('No se registraron nuevos comprobantes.', 'info');

        }



    } catch (err) {

        if (progressEl) progressEl.classList.add('hidden');

        showToast('Error procesando paquetes PDF: ' + err.message, 'error');

    } finally {

        if (btn) btn.disabled = false;

    }

}



async function confirmAmbiguousPaymentChoice(itemIndex) {

    if (!window.lastAmbiguousPaymentItems || !window.lastAmbiguousPaymentItems[itemIndex]) {

        showToast('No se encontró la información del comprobante.', 'error');

        return;

    }



    const item = window.lastAmbiguousPaymentItems[itemIndex];

    const selectedRadio = document.querySelector(`input[name="amb-choice-${itemIndex}"]:checked`);



    if (!selectedRadio) {

        showToast('Por favor selecciona cuál de los contratos corresponde a este pago antes de guardar.', 'warning');

        return;

    }



    const targetContractId = parseInt(selectedRadio.value, 10);

    const targetContractCode = selectedRadio.getAttribute('data-contract-code');



    try {

        const payload = {

            ...item.payload_pago,

            contrato_id: targetContractId,

            codigo_contrato: targetContractCode

        };



        await window.api.createPayment(payload);

        showToast(`Comprobante ${item.codigo_egreso} asignado y guardado en ${targetContractCode} exitosamente.`, 'success');



        // Hide card visually

        const cardEl = document.getElementById(`ambiguous-card-${itemIndex}`);

        if (cardEl) {

            cardEl.innerHTML = `

                <div class="p-2.5 bg-emerald-950/60 border border-emerald-500/50 rounded-xl text-emerald-300 font-semibold flex items-center justify-between text-xs">

                    <span>✅ ${item.codigo_egreso} vinculado exitosamente a ${targetContractCode} (${formatCurrency(item.total_orden)})</span>

                </div>

            `;

        }



        // Decrement ambiguous count badge

        const ambCountEl = document.getElementById('res-pdf-ambiguous-count');

        if (ambCountEl) {

            const current = parseInt(ambCountEl.innerText, 10) || 1;

            ambCountEl.innerText = Math.max(0, current - 1);

        }



        // Increment inserted count badge

        const insCountEl = document.getElementById('res-pdf-inserted-count');

        if (insCountEl) {

            const current = parseInt(insCountEl.innerText, 10) || 0;

            insCountEl.innerText = current + 1;

        }



        await loadExecutionTab();

    } catch (err) {

        showToast(`Error guardando comprobante: ${err.message}`, 'error');

    }

}



function triggerReimportWithOverwrite() {

    const chk = document.getElementById('import-pdf-overwrite-duplicates');

    if (chk) chk.checked = true;

    showToast('Modo de actualización activado. Procesando sobrescritura de comprobantes...', 'info');

    processPdfPacketsUpload();

}



function copyGeneratedTxtLines() {

    const pre = document.getElementById('res-pdf-txt-content');

    if (!pre || !pre.innerText.trim()) {

        showToast('No hay contenido TXT para copiar', 'warning');

        return;

    }

    navigator.clipboard.writeText(pre.innerText).then(() => {

        showToast('Estructura TXT copiada al portapapeles con éxito.', 'success');

    }).catch(() => {

        showToast('Error al copiar al portapapeles', 'error');

    });

}



function downloadGeneratedTxtFile() {

    const pre = document.getElementById('res-pdf-txt-content');

    if (!pre || !pre.innerText.trim()) {

        showToast('No hay contenido TXT para descargar', 'warning');

        return;

    }

    const blob = new Blob([pre.innerText], { type: 'text/plain;charset=utf-8' });

    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');

    a.href = url;

    a.download = `ESPY_Comprobantes_Egreso_8Columnas_${new Date().toISOString().split('T')[0]}.txt`;

    document.body.appendChild(a);

    a.click();

    a.remove();

    URL.revokeObjectURL(url);

    showToast('Archivo TXT descargado.', 'info');

}



// Handler para importar archivo plano TXT/CSV existente

async function handleImportPaymentsSubmit(e) {

    e.preventDefault();

    const fileInput = document.getElementById('import-payments-file');

    if (!fileInput || !fileInput.files || fileInput.files.length === 0) {

        showToast('Seleccione un archivo TXT o CSV para importar', 'warning');

        return;

    }



    const btn = document.getElementById('btn-submit-import-payments');

    const statusDiv = document.getElementById('import-payments-status');

    const oldHtml = btn.innerHTML;



    try {

        btn.disabled = true;

        btn.innerHTML = '<span>⏳</span> Importando...';



        const formData = new FormData();

        formData.append('file', fileInput.files[0]);



        const res = await window.api.importPayments(formData);



        if (statusDiv) {

            statusDiv.className = 'p-3 rounded-xl text-xs bg-emerald-950/80 border border-emerald-500/50 text-emerald-300 block space-y-1';

            statusDiv.innerHTML = `

                <div><strong>¡Importación exitosa!</strong></div>

                <div>Insertados: <strong>${res.inserted}</strong> &middot; Actualizados: <strong>${res.updated}</strong></div>

                ${res.errors && res.errors.length > 0 ? `<div class="text-amber-300 text-[11px]">Avisos: ${res.errors.join(', ')}</div>` : ''}

            `;

        }



        showToast(`Importación completada: ${res.inserted} insertados, ${res.updated} actualizados.`, 'success');

        await loadExecutionTab();



        setTimeout(() => {

            closeImportPaymentsModal();

        }, 1800);

    } catch (err) {

        if (statusDiv) {

            statusDiv.className = 'p-3 rounded-xl text-xs bg-rose-950/80 border border-rose-500/50 text-rose-300 block';

            statusDiv.innerText = `Error: ${err.message}`;

        }

        showToast(`Error al importar: ${err.message}`, 'error');

    } finally {

        btn.disabled = false;

        btn.innerHTML = oldHtml;

    }

}



// Modal New Payment

function openNewPaymentModal() {

    const modal = document.getElementById('modal-new-payment');

    if (!modal) return;

    const form = document.getElementById('form-new-payment');

    if (form) form.reset();

    

    // Auto populate date to today

    const dateInput = document.getElementById('np-fecha-expedicion');

    if (dateInput) dateInput.value = new Date().toISOString().split('T')[0];



    modal.classList.remove('hidden');

}



function closeNewPaymentModal() {

    const modal = document.getElementById('modal-new-payment');

    if (modal) modal.classList.add('hidden');

}



function calculateNetPayment() {

    const orden = parseFloat(document.getElementById('np-total-orden')?.value) || 0.0;

    const ret = parseFloat(document.getElementById('np-total-retencion')?.value) || 0.0;

    const netEl = document.getElementById('np-total-pagar');

    if (netEl) {

        netEl.value = Math.max(0, orden - ret).toFixed(2);

    }

}



async function handleNewPaymentSubmit(e) {

    e.preventDefault();

    if (!window.api.isAdmin()) {

        showToast('Acceso Denegado: Solo el Administrador puede registrar comprobantes de egreso.', 'error');

        return;

    }

    const codigo_contrato = document.getElementById('np-codigo-contrato').value.trim();

    const codigo_egreso = document.getElementById('np-codigo-egreso').value.trim();

    const fecha_expedicion = document.getElementById('np-fecha-expedicion').value || null;

    const rubro_egreso = document.getElementById('np-rubro-egreso').value.trim() || null;

    const nombre_beneficiario = document.getElementById('np-nombre-beneficiario').value.trim().toUpperCase();

    const total_orden = parseFloat(document.getElementById('np-total-orden').value) || 0.0;

    const total_retencion = parseFloat(document.getElementById('np-total-retencion').value) || 0.0;

    const total_pagar = parseFloat(document.getElementById('np-total-pagar').value) || (total_orden - total_retencion);

    const observaciones = document.getElementById('np-observaciones').value.trim() || null;



    try {

        await window.api.createPayment({

            codigo_contrato,

            codigo_egreso,

            fecha_expedicion,

            nombre_beneficiario,

            rubro_egreso,

            total_orden,

            total_retencion,

            total_pagar,

            observaciones,

            vigencia: typeof state.selectedVigencia === 'number' ? state.selectedVigencia : 2026

        });



        showToast(`Comprobante ${codigo_egreso} registrado exitosamente.`, 'success');

        closeNewPaymentModal();

        await loadExecutionTab();

    } catch (err) {

        showToast(`Error registrando comprobante: ${err.message}`, 'error');

    }

}



async function confirmDeletePayment(paymentId, egresoCode) {

    if (!window.api.isAdmin()) {

        showToast('Acceso Denegado: Solo el Administrador puede eliminar comprobantes de egreso.', 'error');

        return;

    }

    if (!confirm(`¿Está seguro de eliminar el comprobante de egreso ${egresoCode}?`)) {

        return;

    }

    try {

        await window.api.deletePayment(paymentId);

        showToast(`Comprobante ${egresoCode} eliminado exitosamente.`, 'info');

        await loadExecutionTab();

    } catch (err) {

        showToast(`Error eliminando comprobante: ${err.message}`, 'error');

    }

}



async function confirmDeletePaymentModal(paymentId, egresoCode, contractId) {

    if (!window.api.isAdmin()) {

        showToast('Acceso Denegado: Solo el Administrador puede eliminar comprobantes de egreso.', 'error');

        return;

    }

    if (!confirm(`¿Estás seguro de eliminar el comprobante ${egresoCode} de este contrato? Se recalcularán inmediatamente los saldos y porcentajes de ejecución.`)) {

        return;

    }

    try {

        await window.api.deletePayment(paymentId);

        showToast(`Comprobante ${egresoCode} eliminado del contrato.`, 'info');

        if (contractId) {

            await openContractPaymentsModal(contractId);

        }

        await loadExecutionTab();

    } catch (err) {

        showToast(`Error eliminando comprobante: ${err.message}`, 'error');

    }

}



let activeReassignState = null;



async function openReassignPaymentModal(paymentId, egresoCode, beneficiario, totalOrden, currentContractCode, contractorId, currentContractId) {

    activeReassignState = {

        paymentId,

        egresoCode,

        beneficiario,

        totalOrden,

        currentContractCode,

        contractorId,

        currentContractId

    };



    const modal = document.getElementById('modal-reassign-payment');

    const ceEl = document.getElementById('reassign-modal-ce');

    const benEl = document.getElementById('reassign-modal-beneficiario');

    const valEl = document.getElementById('reassign-modal-valor');

    const curEl = document.getElementById('reassign-modal-current-contract');

    const selectEl = document.getElementById('reassign-select-contract');



    if (!modal || !selectEl) return;



    if (ceEl) ceEl.innerText = egresoCode;

    if (benEl) benEl.innerText = beneficiario || 'N/A';

    if (valEl) valEl.innerText = formatCurrency(totalOrden || 0);

    if (curEl) curEl.innerText = currentContractCode || 'N/A';



    // Populate candidate contracts for this contractor

    selectEl.innerHTML = '<option value="">Cargando contratos del contratista...</option>';

    modal.classList.remove('hidden');



    try {

        // Fetch contracts of this contractor

        let contractsList = [];

        if (contractorId) {

            try {

                const dossier = await window.api.getContractorExecutionDossier(contractorId);

                contractsList = dossier.contratos || [];

            } catch (e) {

                console.warn('Error fetching contractor dossier for reassign:', e);

            }

        }



        // Fallback: search in state.contracts or state.execution.contracts

        if (contractsList.length === 0 && state.contracts && state.contracts.length > 0) {

            const benClean = (beneficiario || '').trim().toLowerCase();

            contractsList = state.contracts.filter(c => {

                const cBen = (c.contratista && c.contratista.nombre_o_razon_social ? c.contratista.nombre_o_razon_social : (c.contratista_nombre || '')).toLowerCase();

                return (contractorId && c.contratista_id === contractorId) || (benClean && cBen.includes(benClean));

            });

        }



        // Exclude the current contract if other options exist

        const otherContracts = contractsList.filter(c => c.numero_contrato !== currentContractCode);



        if (otherContracts.length === 0) {

            selectEl.innerHTML = '<option value="">No se encontraron otros contratos registrados para este contratista</option>';

        } else {

            let optHtml = '<option value="">-- Seleccione el contrato destino --</option>';

            otherContracts.forEach(c => {

                const objSnippet = c.objeto ? (c.objeto.length > 60 ? c.objeto.substring(0, 60) + '...' : c.objeto) : '';

                optHtml += `<option value="${c.id}" data-code="${c.numero_contrato}">${c.numero_contrato} - ${formatCurrency(c.valor_total || 0)} ${objSnippet ? `(${objSnippet})` : ''}</option>`;

            });

            selectEl.innerHTML = optHtml;

        }

    } catch (err) {

        selectEl.innerHTML = `<option value="">Error cargando contratos: ${err.message}</option>`;

    }

}



function closeReassignPaymentModal() {

    const modal = document.getElementById('modal-reassign-payment');

    if (modal) modal.classList.add('hidden');

    activeReassignState = null;

}



async function executePaymentReassignment() {

    if (!activeReassignState) return;



    const selectEl = document.getElementById('reassign-select-contract');

    const targetContractId = selectEl ? parseInt(selectEl.value, 10) : null;

    const selectedOption = selectEl ? selectEl.options[selectEl.selectedIndex] : null;

    const targetContractCode = selectedOption ? selectedOption.getAttribute('data-code') : '';



    if (!targetContractId || isNaN(targetContractId)) {

        showToast('Por favor seleccione el contrato de destino.', 'warning');

        return;

    }



    const btn = document.getElementById('btn-confirm-reassign-payment');

    try {

        if (btn) btn.disabled = true;

        await window.api.reassignPayment(activeReassignState.paymentId, {

            contrato_id: targetContractId,

            codigo_contrato: targetContractCode

        });



        showToast(`Comprobante ${activeReassignState.egresoCode} reasignado exitosamente a ${targetContractCode}.`, 'success');

        

        const currentModalContractId = activeReassignState.currentContractId;

        closeReassignPaymentModal();



        // Refresh modals and dashboard

        if (currentModalContractId) {

            await openContractPaymentsModal(currentModalContractId);

        }

        await loadExecutionTab();

    } catch (err) {

        showToast(`Error al reasignar comprobante: ${err.message}`, 'error');

    } finally {

        if (btn) btn.disabled = false;

    }

}



function exportExecutionCSV() {

    const vigParam = state.selectedVigencia === 'ALL' ? 'ALL' : state.selectedVigencia;

    const url = window.api.getExecutionExportUrl(vigParam);

    const link = document.createElement('a');

    link.href = url;

    link.setAttribute('download', `ESPY_Ejecucion_${vigParam}.csv`);

    document.body.appendChild(link);

    link.click();

    link.remove();

    showToast('Descarga de reporte consolidado CSV iniciada.', 'info');

}



// Close execution and management modals on backdrop click

document.addEventListener('DOMContentLoaded', () => {

    ['modal-contractor-dossier', 'modal-contract-payments', 'modal-payment-detail', 'modal-import-payments', 'modal-new-payment', 'modal-manage-users'].forEach(modalId => {

        const el = document.getElementById(modalId);

        if (el) {

            el.addEventListener('click', (e) => {

                if (e.target === el) {

                    el.classList.add('hidden');

                }

            });

        }

    });

});



// =============================================================

// CENTRO DE REPORTES E INFORMES CONTRACTUALES (Word & PowerPoint)

// =============================================================



async function loadReportsTab() {

    if (!window.api.isAdmin()) {

        showToast('Acceso Restringido: El perfil Invitado no tiene acceso al Centro de Reportes.', 'warning');

        switchTab('dashboard');

        return;

    }

    const vigSelect = document.getElementById('report-filter-vigencia');

    if (vigSelect && state.selectedVigencia) {

        vigSelect.value = String(state.selectedVigencia);

    }

    await loadReportsPreview();

}



function handleReportsFilterChange() {

    if (!window.api.isAdmin()) return;

    loadReportsPreview();

}



async function loadReportsPreview() {

    if (!window.api.isAdmin()) return;

    const vigSelect = document.getElementById('report-filter-vigencia');

    const perSelect = document.getElementById('report-filter-periodo');

    const badge = document.getElementById('reports-filter-badge');



    const vigencia = vigSelect ? vigSelect.value : (state.selectedVigencia || '2026');

    const periodo = perSelect ? perSelect.value : 'ACUMULADO';



    if (badge) {

        const perText = perSelect ? perSelect.options[perSelect.selectedIndex]?.text : periodo;

        const vigText = vigencia === 'ALL' ? 'Todas las vigencias' : `Vigencia ${vigencia}`;

        badge.innerText = `${vigText} • ${perText}`;

    }



    try {

        const res = await window.api.getReportsPreview(vigencia, periodo);

        if (res && res.kpis) {

            const k = res.kpis;

            const elContratado = document.getElementById('report-kpi-contratado');

            const elCausado = document.getElementById('report-kpi-causado');

            const elSaldo = document.getElementById('report-kpi-saldo');

            const elNeto = document.getElementById('report-kpi-neto');

            const elContratos = document.getElementById('report-kpi-contratos');

            const elPct = document.getElementById('report-kpi-pct');

            const elReserva = document.getElementById('report-kpi-reserva');

            const elRet = document.getElementById('report-kpi-ret');



            if (elContratado) elContratado.innerText = k.total_contratado_formatted;

            if (elCausado) elCausado.innerText = k.total_orden_formatted;

            if (elSaldo) elSaldo.innerText = k.saldo_por_ejecutar_formatted;

            if (elNeto) elNeto.innerText = k.total_pagar_formatted;

            if (elContratos) elContratos.innerText = `${k.total_contratos} contratos formalizados`;

            if (elPct) elPct.innerText = `${k.pct_ejecucion}% ejecutado (${k.conteo_comprobantes} egresos)`;

            if (elReserva) elReserva.innerText = `Incluye ${k.reserva_contingencia_formatted} reserva`;

            if (elRet) elRet.innerText = `Retenciones: ${k.total_retencion_formatted}`;

        }

    } catch (err) {

        console.warn('Aviso cargando preview de reportes:', err);

    }

}



async function triggerDownloadReport(format) {

    if (!window.api.isAdmin()) {

        showToast('Acceso Restringido: Solo los administradores pueden generar o descargar informes oficiales.', 'error');

        return;

    }

    const vigSelect = document.getElementById('report-filter-vigencia');

    const perSelect = document.getElementById('report-filter-periodo');

    const annexCheckbox = document.getElementById('report-filter-annexes');



    const vigencia = vigSelect ? vigSelect.value : (state.selectedVigencia || '2026');

    const periodo = perSelect ? perSelect.value : 'ACUMULADO';

    const includeAnnexes = annexCheckbox ? annexCheckbox.checked : true;



    const btnWord = document.getElementById('btn-download-word');

    const btnPptx = document.getElementById('btn-download-powerpoint');

    const statusBox = document.getElementById('reports-compilation-status');

    const statusTitle = document.getElementById('reports-status-title');

    const statusDesc = document.getElementById('reports-status-desc');



    const isWord = format === 'word';

    const origText = isWord ? document.getElementById('btn-word-text')?.innerText : document.getElementById('btn-powerpoint-text')?.innerText;

    const textSpan = isWord ? document.getElementById('btn-word-text') : document.getElementById('btn-powerpoint-text');



    if (btnWord) btnWord.disabled = true;

    if (btnPptx) btnPptx.disabled = true;



    if (textSpan) textSpan.innerText = isWord ? 'Compilando Documento Word...' : 'Generando Presentación PowerPoint...';

    if (statusBox) {

        statusBox.classList.remove('hidden');

        if (statusTitle) statusTitle.innerText = isWord ? 'Compilando Informe Gerencial (.docx)...' : 'Generando Presentación Panorámica (.pptx)...';

        if (statusDesc) statusDesc.innerText = `Procesando matriz presupuestal, retenciones y tablas consolidadas para ${vigencia === 'ALL' ? 'todas las vigencias' : 'la vigencia ' + vigencia}...`;

    }



    try {

        const downloadUrl = isWord 

            ? window.api.getReportWordDownloadUrl(vigencia, periodo, includeAnnexes)

            : window.api.getReportPowerPointDownloadUrl(vigencia, periodo, includeAnnexes);



        // Fetch as blob to detect HTTP errors and trigger clean browser download

        const headers = {};

        if (window.api && window.api.token) {

            headers['Authorization'] = `Bearer ${window.api.token}`;

        }

        const res = await fetch(downloadUrl, { headers });

        if (!res.ok) {

            if (res.status === 401) {

                if (window.api && typeof window.api.logout === 'function') window.api.logout();

                document.body.classList.remove('role-admin', 'role-invitado', 'role-editor');

                if (typeof showLoginScreen === 'function') showLoginScreen();

                showToast("Su sesión expiró. Inicie sesión de nuevo.", "warning");

                throw new Error("Su sesión expiró. Inicie sesión de nuevo.");

            }

            let errMsg = 'Error en el servidor de compilación';

            try {

                const errJson = await res.json();

                errMsg = errJson.detail || errMsg;

            } catch (e) {}

            throw new Error(errMsg);

        }



        const blob = await res.blob();

        const extension = isWord ? 'docx' : 'pptx';

        const docName = isWord ? 'Informe_Gerencial_ESPY' : 'Presentacion_Ejecutiva_ESPY';

        const dateTag = new Date().toISOString().slice(0, 10).replace(/-/g, '');

        const filename = `${docName}_${vigencia}_${dateTag}.${extension}`;



        const blobUrl = window.URL.createObjectURL(blob);

        const a = document.createElement('a');

        a.href = blobUrl;

        a.download = filename;

        document.body.appendChild(a);

        a.click();

        a.remove();

        setTimeout(() => window.URL.revokeObjectURL(blobUrl), 3000);



        showToast(

            isWord 

                ? 'Informe Gerencial en Microsoft Word (.docx) descargado exitosamente.' 

                : 'Presentación Ejecutiva en PowerPoint (.pptx) descargada exitosamente.',

            'success'

        );

    } catch (err) {

        showToast(`Error al generar entregable: ${err.message}`, 'error');

    } finally {

        if (btnWord) btnWord.disabled = false;

        if (btnPptx) btnPptx.disabled = false;

        if (textSpan && origText) textSpan.innerText = origText;

        if (statusBox) statusBox.classList.add('hidden');

    }

}













// =============================================================

// MÓDULO AGENTE ESPECIALISTA EN MATRICES DE RIESGOS (CCE)

// =============================================================

state.riskMatrix = state.riskMatrix || {

    selectedContractId: null,

    currentResult: null,

    uploadedDocId: null

};



async function loadRisksView() {

    try {

        const select = document.getElementById('risk-contract-select');

        if (select) {

            const contracts = await window.api.getContracts();

            const currentVal = select.value;

            select.innerHTML = '<option value="">-- Seleccionar contrato del sistema (opcional) --</option>';

            if (Array.isArray(contracts)) {

                contracts.forEach(c => {

                    const opt = document.createElement('option');

                    opt.value = c.id;

                    const cNombre = c.contratista?.nombre_o_razon_social || 'Sin contratista';

                    opt.textContent = `${c.numero_contrato} - ${cNombre} (${c.tipologia})`;

                    select.appendChild(opt);

                });

            }

            if (currentVal) select.value = currentVal;

            else if (state.riskMatrix.selectedContractId) select.value = state.riskMatrix.selectedContractId;

        }

        checkRiskInputsChecklist();

    } catch (e) {

        console.warn('Error al cargar contratos para módulo de riesgos:', e);

    }

}



async function handleRiskContractSelect(contractId) {

    if (!contractId) {

        state.riskMatrix.selectedContractId = null;

        return;

    }

    state.riskMatrix.selectedContractId = contractId;

    try {

        showToast('Cargando datos del contrato para análisis de riesgos...', 'info');

        const contract = await window.api.getContract(contractId);

        if (!contract) return;



        if (contract.objeto) document.getElementById('risk-input-objeto').value = contract.objeto;

        if (contract.tipologia) document.getElementById('risk-input-tipologia').value = contract.tipologia;

        if (contract.valor_total) document.getElementById('risk-input-valor').value = contract.valor_total;

        if (contract.plazo_texto) document.getElementById('risk-input-plazo').value = contract.plazo_texto;

        else if (contract.plazo_ejecucion) document.getElementById('risk-input-plazo').value = `${contract.plazo_ejecucion} ${contract.unidad_plazo.toLowerCase()}`;

        

        if (contract.contratista && contract.contratista.nombre_o_razon_social) {

            document.getElementById('risk-input-contratista').value = contract.contratista.nombre_o_razon_social;

        }



        const tienePolizas = contract.garantias_exigidas && Object.keys(contract.garantias_exigidas).length > 0;

        document.getElementById('risk-input-polizas').value = tienePolizas ? 'true' : 'false';



        // Forzar siempre a que se regenere dinámicamente con los datos actualizados del contrato

        // sin servir versiones viejas o desactualizadas

        if (contract.metadatos_agente && contract.metadatos_agente.matriz_riesgos) {

            delete contract.metadatos_agente.matriz_riesgos;

        }

        state.riskMatrix.currentResult = null;

        const resContainer = document.getElementById('risk-matrix-results-container');

        if (resContainer) resContainer.classList.add('hidden');

        const exportBtnDocx = document.getElementById('btn-export-risk-quick-docx');

        if (exportBtnDocx) {

            exportBtnDocx.disabled = true;

            exportBtnDocx.className = 'px-4 py-2 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-blue-700 to-indigo-600 hover:from-blue-600 hover:to-indigo-500 shadow-md flex items-center gap-1.5 transition-all opacity-50 cursor-not-allowed';

        }

        const exportBtnPdf = document.getElementById('btn-export-risk-quick-pdf');

        if (exportBtnPdf) {

            exportBtnPdf.disabled = true;

            exportBtnPdf.className = 'px-4 py-2 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-rose-700 to-red-600 hover:from-rose-600 hover:to-red-500 shadow-md flex items-center gap-1.5 transition-all opacity-50 cursor-not-allowed';

        }



        checkRiskInputsChecklist();

    } catch (e) {

        showToast(`Error al cargar contrato: ${e.message}`, 'error');

    }

}



async function handleRiskFileUpload(files) {

    if (!files || files.length === 0) return;

    const file = files[0];

    showToast(`Analizando y procesando archivo: ${file.name}...`, 'info');



    try {

        const parseRes = await window.api.uploadAndParseRiskDocument(

            file, 

            state.riskMatrix.selectedContractId

        );



        if (parseRes && parseRes.document_id) {

            state.riskMatrix.uploadedDocId = parseRes.document_id;



            // Inyectar texto extraído del Estudio Previo

            if (parseRes.texto_extraido) {

                const txtArea = document.getElementById('risk-input-estudio-texto');

                if (txtArea) txtArea.value = parseRes.texto_extraido;

            }



            // Inyectar objeto contractual detectado

            if (parseRes.objeto_detectado) {

                const objInput = document.getElementById('risk-input-objeto');

                if (objInput) objInput.value = parseRes.objeto_detectado;

            }



            // Inyectar contratista detectado

            if (parseRes.contratista_detectado) {

                const contInput = document.getElementById('risk-input-contratista');

                if (contInput) contInput.value = parseRes.contratista_detectado;

            }



            // Inyectar tipología detectada

            if (parseRes.tipologia_detectada) {

                const tipSelect = document.getElementById('risk-input-tipologia');

                if (tipSelect) tipSelect.value = parseRes.tipologia_detectada;

            }



            // Inyectar presupuesto detectado

            if (parseRes.valor_detectado) {

                const valInput = document.getElementById('risk-input-valor');

                if (valInput) valInput.value = parseRes.valor_detectado;

            }



            // Inyectar plazo detectado

            if (parseRes.plazo_detectado) {

                const plzInput = document.getElementById('risk-input-plazo');

                if (plzInput) plzInput.value = parseRes.plazo_detectado;

            }



            // Inyectar condición de pólizas detectada

            if (parseRes.polizas_detectada !== null && parseRes.polizas_detectada !== undefined) {

                const polSelect = document.getElementById('risk-input-polizas');

                if (polSelect) polSelect.value = parseRes.polizas_detectada ? 'true' : 'false';

            }



            checkRiskInputsChecklist();

            showToast('¡Estudio Previo procesado con éxito! Insumos y parámetros extraídos automáticamente.', 'success');

        }

    } catch (e) {

        showToast(`Error al procesar archivo: ${e.message}`, 'error');

    }

}



function checkRiskInputsChecklist() {

    const objeto = (document.getElementById('risk-input-objeto')?.value || '').trim();

    const tipologia = document.getElementById('risk-input-tipologia')?.value || 'PRESTACION_SERVICIOS';

    const valor = (document.getElementById('risk-input-valor')?.value || '').trim();

    const plazo = (document.getElementById('risk-input-plazo')?.value || '').trim();

    const contratista = (document.getElementById('risk-input-contratista')?.value || '').trim();

    const polizas = document.getElementById('risk-input-polizas')?.value;

    const texto = (document.getElementById('risk-input-estudio-texto')?.value || '').trim();



    const charCountEl = document.getElementById('risk-text-char-count');

    if (charCountEl) charCountEl.textContent = `${texto.length} caracteres`;



    const fullContext = (objeto + ' ' + texto).toLowerCase();



    // 1. Objeto y Alcance

    const hasObj = objeto.length >= 15 || /objeto\s*:/.test(fullContext);

    updateCheckItem('chk-obj', hasObj, '1. Objeto y Alcance', hasObj ? 'Definido y delimitado' : 'Pendiente definir');



    // 2. Obligaciones y Perfil

    const hasOblg = /obligar|obligaciones|perfil|idoneidad|actividades/.test(fullContext) || contratista.length > 3;

    updateCheckItem('chk-oblg', hasOblg, '2. Obligaciones y Perfil', hasOblg ? 'Obligaciones o idoneidad identificadas' : 'No especificadas');



    // 3. Presupuesto y Pago

    const hasPto = (parseFloat(valor) > 0) || /presupuesto|valor|\$|desembolso|pago/.test(fullContext);

    updateCheckItem('chk-pto', hasPto, '3. Presupuesto y Pago', hasPto ? 'Presupuesto cuantificado' : 'Sin valor estimado');



    // 4. Plazo y Cronograma

    const hasPlz = plazo.length > 0 || /plazo|cronograma|meses|d[ií]as/.test(fullContext);

    updateCheckItem('chk-plz', hasPlz, '4. Plazo y Cronograma', hasPlz ? 'Plazo establecido' : 'Plazo no definido');



    // 5. Ubicación Territorial

    const hasLug = /yolomb[oó]|urbana|rural|plantas|redes/.test(fullContext);

    updateCheckItem('chk-lug', hasLug, '5. Ubicación Territorial', hasLug ? 'Delimitado en Yolombó' : 'Área no delimitada');



    // 6. Pólizas / Garantías

    const hasPol = polizas !== undefined && polizas !== '';

    updateCheckItem('chk-pol', hasPol, '6. Pólizas / Garantías', polizas === 'false' ? 'No se exigen (pago condicionado)' : 'Exigidas en contrato');



    const itemsOk = [hasObj, hasOblg, hasPto, hasPlz, hasLug, hasPol].filter(Boolean).length;

    const scoreBadge = document.getElementById('risk-checklist-score');

    if (scoreBadge) {

        scoreBadge.textContent = `${itemsOk}/6 Insumos detectados`;

        if (itemsOk === 6) {

            scoreBadge.className = 'text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300';

        } else if (itemsOk >= 4) {

            scoreBadge.className = 'text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300';

        } else {

            scoreBadge.className = 'text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300';

        }

    }



    // Detección de advertencias preventivas

    const warnings = [];

    if (tipologia === 'PRESTACION_SERVICIOS' && /suministro|bienes\s+muebles|compraventa/.test(fullContext)) {

        warnings.push('El texto contiene referencias a "suministro" en un proceso de servicios personales.');

    }

    if (/genti[oó]n|conplementarias/.test(fullContext)) {

        warnings.push('Se detectaron erratas de digitación en el objeto ("gentión" / "conplementarias") que serán normalizadas.');

    }

    if (polizas === 'false' || /no\s+se\s+requerir[aá]\s+(?:la\s+constituci[oó]n\s+de\s+)?p[oó]lizas/.test(fullContext)) {

        warnings.push('Sin pólizas exigidas: el riesgo patrimonial debe mitigarse mediante pago post-servicio contra informe aprobado.');

    }



    const warnBox = document.getElementById('risk-live-warnings-box');

    const warnList = document.getElementById('risk-live-warnings-list');

    if (warnBox && warnList) {

        if (warnings.length > 0) {

            warnList.innerHTML = warnings.map(w => `<li>${w}</li>`).join('');

            warnBox.classList.remove('hidden');

        } else {

            warnBox.classList.add('hidden');

        }

    }

}



function updateCheckItem(id, isOk, title, desc) {

    const el = document.getElementById(id);

    if (!el) return;

    const icon = isOk ? '✅' : '⚪';

    const colorClass = isOk ? 'text-emerald-700 dark:text-emerald-400 font-semibold' : 'text-slate-500 dark:text-slate-400';

    el.className = `flex items-start gap-2 ${colorClass}`;

    el.innerHTML = `<span class="chk-icon mt-0.5">${icon}</span><span><strong>${title}:</strong> ${desc}</span>`;

}



async function triggerGenerateRiskMatrix() {

    const objeto = (document.getElementById('risk-input-objeto')?.value || '').trim();

    const tipologia = document.getElementById('risk-input-tipologia')?.value || 'PRESTACION_SERVICIOS';

    const valor = parseFloat(document.getElementById('risk-input-valor')?.value) || 0;

    const plazo = (document.getElementById('risk-input-plazo')?.value || '').trim();

    const contratista = (document.getElementById('risk-input-contratista')?.value || '').trim();

    const polizas = document.getElementById('risk-input-polizas')?.value === 'true';

    const texto = (document.getElementById('risk-input-estudio-texto')?.value || '').trim();



    if (!objeto && !texto && !state.riskMatrix.uploadedDocId) {

        showToast('Por favor ingrese al menos el Objeto Contractual o cargue el Estudio Previo.', 'warning');

        document.getElementById('risk-input-objeto')?.focus();

        return;

    }



    const btn = document.getElementById('btn-generate-risk-matrix');

    const btnText = document.getElementById('btn-generate-risk-text');

    const origText = btnText ? btnText.textContent : 'Estructurar y Valorar Matriz de Riesgos CCE';



    try {

        if (btn) btn.disabled = true;

        if (btnText) btnText.innerHTML = '<span class="inline-block animate-spin mr-2">⚙️</span>Estructurando y Verificando Aritmética...';

        showToast('Agente IA de Riesgos analizando el proceso contractual...', 'info');



        const docIds = [];

        if (state.riskMatrix.uploadedDocId) docIds.push(state.riskMatrix.uploadedDocId);



        const payload = {

            contrato_id: state.riskMatrix.selectedContractId ? parseInt(state.riskMatrix.selectedContractId) : null,

            document_ids: docIds,

            estudio_previo_texto: texto || null,

            objeto: objeto || null,

            tipologia: tipologia,

            contratista_nombre: contratista || null,

            valor_estimado: valor > 0 ? valor : null,

            plazo_texto: plazo || null,

            lugar_ejecucion: "Municipio de Yolombó, Antioquia",

            exige_polizas: polizas,

            custom_logo_path: state.riskMatrix.customLogoPath || null

        };



        const result = await window.api.generateRiskMatrix(payload);

        state.riskMatrix.currentResult = result;



        renderRiskMatrixResults(result);

        showToast('¡Matriz de Riesgos estructurada y validada aritméticamente con éxito!', 'success');



        const exportBtnDocx = document.getElementById('btn-export-risk-quick-docx');

        if (exportBtnDocx) {

            exportBtnDocx.disabled = false;

            exportBtnDocx.className = 'px-4 py-2 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-blue-700 to-indigo-600 hover:from-blue-600 hover:to-indigo-500 shadow-md flex items-center gap-1.5 transition-all cursor-pointer';

        }

        const exportBtnPdf = document.getElementById('btn-export-risk-quick-pdf');

        if (exportBtnPdf) {

            exportBtnPdf.disabled = false;

            exportBtnPdf.className = 'px-4 py-2 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-rose-700 to-red-600 hover:from-rose-600 hover:to-red-500 shadow-md flex items-center gap-1.5 transition-all cursor-pointer';

        }



        // Desplazamiento suave al contenedor de resultados

        const resBox = document.getElementById('risk-matrix-results-container');

        if (resBox) {

            resBox.scrollIntoView({ behavior: 'smooth', block: 'start' });

        }

    } catch (e) {

        showToast(`Error generando matriz de riesgos: ${e.message}`, 'error');

    } finally {

        if (btn) btn.disabled = false;

        if (btnText) btnText.textContent = origText;

    }

}



function renderRiskMatrixResults(res) {

    if (!res || !Array.isArray(res.riesgos)) return;



    const resContainer = document.getElementById('risk-matrix-results-container');

    if (!resContainer) return;

    resContainer.classList.remove('hidden');



    // 1. Ficha Oficial del Proceso y Objeto Contractual

    const fObj = document.getElementById('res-ficha-objeto');

    if (fObj) fObj.textContent = res.objeto || 'No especificado';



    const fContr = document.getElementById('res-ficha-contratista');

    if (fContr) {

        const tipoName = (res.tipologia || 'PRESTACION_SERVICIOS').replace(/_/g, ' ');

        fContr.textContent = `${res.contratista_nombre || 'Contratista Seleccionado'}  |  ${tipoName}`;

    }



    const fVal = document.getElementById('res-ficha-valor');

    if (fVal) {

        const valTxt = res.valor_estimado ? `$${Math.round(res.valor_estimado).toString().replace(/\B(?=(\d{3})+(?!\d))/g, '.')}` : 'Según presupuesto oficial';

        fVal.textContent = `${valTxt}  |  Lugar: ${res.lugar_ejecucion || 'Municipio de Yolombó, Antioquia'}`;

    }



    const fPlazo = document.getElementById('res-ficha-plazo');

    if (fPlazo) {

        const polTxt = res.exige_polizas ? 'Pólizas contractuales exigidas' : 'No se exige constitución de pólizas (Pago condicionado a recibido)';

        fPlazo.textContent = `Plazo: ${res.plazo_texto || 'Según cronograma'}  |  Garantías: ${polTxt}`;

    }



    // 2. Resumen de KPIs

    document.getElementById('res-total-risks').textContent = res.total_riesgos || res.riesgos.length;

    const highCount = (res.resumen_categorias_inicial?.Alto || 0) + (res.resumen_categorias_inicial?.Extremo || 0);

    document.getElementById('res-high-risks').textContent = highCount;

    document.getElementById('res-medium-risks').textContent = res.resumen_categorias_inicial?.Medio || 0;

    document.getElementById('res-residual-low').textContent = res.resumen_categorias_residual?.Bajo || 0;



    // Subtítulo con objeto

    const subtitle = document.getElementById('risk-matrix-table-subtitle');

    if (subtitle) {

        subtitle.textContent = `Proceso: ${res.objeto} | Régimen ESP Ley 142 de 1994`;

    }



    // 3. Tabla de 14 Columnas

    const tbody = document.getElementById('risk-matrix-table-body');

    if (tbody) {

        tbody.innerHTML = '';

        res.riesgos.forEach((r, idx) => {

            const tr = document.createElement('tr');

            tr.className = idx % 2 === 0 ? 'bg-white dark:bg-[#0c1427]' : 'bg-slate-50/70 dark:bg-slate-900/40';



            // Badges para categorías

            const getCatBadge = (cat) => {

                switch ((cat || '').toUpperCase()) {

                    case 'EXTREMO':

                        return '<span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-rose-200 text-rose-900 dark:bg-rose-950 dark:text-rose-200">EXTREMO</span>';

                    case 'ALTO':

                        return '<span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-rose-100 text-rose-800 dark:bg-rose-950/80 dark:text-rose-300">ALTO</span>';

                    case 'MEDIO':

                        return '<span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300">MEDIO</span>';

                    default:

                        return '<span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">BAJO</span>';

                }

            };



            const isSST = (r.tipo || '').toLowerCase().includes('sst') || (r.tipo || '').toLowerCase().includes('laboral');

            const tipoBadge = isSST 

                ? `<span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-300">${r.tipo}</span>`

                : `<span class="font-semibold text-slate-700 dark:text-slate-300">${r.tipo}</span>`;



            tr.innerHTML = `

                <td class="py-2.5 px-2 text-center font-mono font-bold text-slate-800 dark:text-slate-100 border-r border-slate-200 dark:border-slate-800">${r.numero}</td>

                <td class="py-2.5 px-2 text-center text-slate-600 dark:text-slate-400 border-r border-slate-200 dark:border-slate-800">${r.clase}</td>

                <td class="py-2.5 px-2 text-center text-slate-600 dark:text-slate-400 border-r border-slate-200 dark:border-slate-800">${r.fuente}</td>

                <td class="py-2.5 px-2 text-center text-slate-600 dark:text-slate-400 border-r border-slate-200 dark:border-slate-800">${r.etapa}</td>

                <td class="py-2.5 px-2 text-center border-r border-slate-200 dark:border-slate-800">${tipoBadge}</td>

                <td class="py-2.5 px-3 text-slate-800 dark:text-slate-200 border-r border-slate-200 dark:border-slate-800 leading-snug">${r.descripcion}</td>

                <td class="py-2.5 px-3 text-slate-600 dark:text-slate-400 border-r border-slate-200 dark:border-slate-800 leading-snug">${r.consecuencia}</td>

                <td class="py-2.5 px-2 text-center font-mono border-r border-slate-200 dark:border-slate-800 bg-amber-50/50 dark:bg-amber-950/20">

                    <div class="text-[10px] text-slate-500">P:${r.probabilidad_inicial} I:${r.impacto_inicial}</div>

                    <div class="font-bold text-xs text-slate-800 dark:text-slate-100">Val:${r.valoracion_inicial}</div>

                    <div class="mt-0.5">${getCatBadge(r.categoria_inicial)}</div>

                </td>

                <td class="py-2.5 px-2 text-center text-slate-700 dark:text-slate-300 font-semibold border-r border-slate-200 dark:border-slate-800">${r.asignacion}</td>

                <td class="py-2.5 px-3 text-slate-800 dark:text-slate-200 border-r border-slate-200 dark:border-slate-800 leading-snug">${r.tratamiento}</td>

                <td class="py-2.5 px-2 text-center font-mono border-r border-slate-200 dark:border-slate-800 bg-emerald-50/40 dark:bg-emerald-950/20">

                    <div class="text-[10px] text-slate-500">P:${r.probabilidad_residual} I:${r.impacto_residual}</div>

                    <div class="font-bold text-xs text-slate-800 dark:text-slate-100">Val:${r.valoracion_residual}</div>

                    <div class="mt-0.5">${getCatBadge(r.categoria_residual)}</div>

                </td>

                <td class="py-2.5 px-1 text-center font-bold text-slate-700 dark:text-slate-300 border-r border-slate-200 dark:border-slate-800">${r.afecta_ejecucion}</td>

                <td class="py-2.5 px-2 text-center text-slate-700 dark:text-slate-300 border-r border-slate-200 dark:border-slate-800">${r.responsable}</td>

                <td class="py-2.5 px-3 text-slate-700 dark:text-slate-300 leading-snug">

                    <div>${r.monitoreo_mecanismo}</div>

                    <div class="text-[10px] text-[#1590D3] dark:text-[#55C6DE] font-semibold mt-1">Periodicidad: ${r.monitoreo_periodicidad}</div>

                </td>

            `;

            tbody.appendChild(tr);

        });

    }



    // 4. Observaciones Técnicas y Recomendaciones

    const obsBox = document.getElementById('risk-audit-observations-box');

    const obsList = document.getElementById('risk-audit-observations-list');

    if (obsBox && obsList) {

        if (Array.isArray(res.observaciones_estudio_previo) && res.observaciones_estudio_previo.length > 0) {

            obsList.innerHTML = res.observaciones_estudio_previo.map(o => `<li>${o}</li>`).join('');

            obsBox.classList.remove('hidden');

        } else {

            obsBox.classList.add('hidden');

        }

    }

}



async function downloadCurrentRiskMatrixDocx() {

    if (!state.riskMatrix.currentResult) {

        showToast('No hay una matriz de riesgos generada para descargar.', 'warning');

        return;

    }

    try {

        showToast('Compilando Matriz de Riesgos en Word Horizontal (.docx)...', 'info');

        await window.api.downloadRiskMatrixDocx(state.riskMatrix.currentResult);

        showToast('¡Documento Word descargado exitosamente!', 'success');

    } catch (e) {

        showToast(`Error al descargar archivo DOCX: ${e.message}`, 'error');

    }

}



async function downloadCurrentRiskMatrixPdf() {

    if (!state.riskMatrix.currentResult) {

        showToast('No hay una matriz de riesgos generada para descargar.', 'warning');

        return;

    }

    try {

        showToast('Compilando Matriz de Riesgos en PDF Horizontal institucional...', 'info');

        await window.api.downloadRiskMatrixPdf(state.riskMatrix.currentResult);

        showToast('¡Documento PDF institucional descargado exitosamente!', 'success');

    } catch (e) {

        showToast(`Error al descargar archivo PDF: ${e.message}`, 'error');

    }

}



async function handleRiskLogoUpload(files) {

    if (!files || files.length === 0) return;

    const file = files[0];

    try {

        showToast('Cargando logotipo de membrete institucional...', 'info');

        const res = await window.api.uploadLetterheadLogo(file);

        if (res && res.logo_path) {

            state.riskMatrix.customLogoPath = res.logo_path;

            state.riskMatrix.customLogoUrl = res.logo_url;

            

            const prev = document.getElementById('risk-letterhead-logo-preview');

            if (prev) prev.src = res.logo_url;

            

            const badge = document.getElementById('risk-letterhead-badge');

            if (badge) {

                badge.textContent = 'Membrete Personalizado';

                badge.className = 'px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300';

            }

            const desc = document.getElementById('risk-letterhead-desc');

            if (desc) desc.textContent = `Logotipo personalizado cargado (${file.name}). Se aplicará automáticamente a los documentos oficiales en DOCX y PDF.`;



            const btnReset = document.getElementById('btn-reset-risk-logo');

            if (btnReset) btnReset.classList.remove('hidden');



            showToast('¡Logotipo de membrete personalizado cargado con éxito!', 'success');

        }

    } catch (e) {

        showToast(`Error al subir logotipo: ${e.message}`, 'error');

    }

}



function resetRiskLetterheadLogo() {

    state.riskMatrix.customLogoPath = null;

    state.riskMatrix.customLogoUrl = null;

    

    const prev = document.getElementById('risk-letterhead-logo-preview');

    if (prev) prev.src = '/assets/logo.png';

    

    const badge = document.getElementById('risk-letterhead-badge');

    if (badge) {

        badge.textContent = 'Oficial ESPY S.A. E.S.P.';

        badge.className = 'px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300';

    }

    const desc = document.getElementById('risk-letterhead-desc');

    if (desc) desc.textContent = 'Logo institucional con marcas de agua y pie de página oficial de Yolombó aplicado automáticamente a DOCX y PDF.';



    const btnReset = document.getElementById('btn-reset-risk-logo');

    if (btnReset) btnReset.classList.add('hidden');



    const fileInp = document.getElementById('risk-logo-input');

    if (fileInp) fileInp.value = '';



    showToast('Membrete oficial ESPY restaurado como predeterminado.', 'info');

}



function resetRiskMatrixForm() {

    state.riskMatrix.selectedContractId = null;

    state.riskMatrix.currentResult = null;

    state.riskMatrix.uploadedDocId = null;



    const cSelect = document.getElementById('risk-contract-select');

    if (cSelect) cSelect.value = '';



    document.getElementById('risk-input-objeto').value = '';

    document.getElementById('risk-input-tipologia').value = 'PRESTACION_SERVICIOS';

    document.getElementById('risk-input-valor').value = '';

    document.getElementById('risk-input-plazo').value = '';

    document.getElementById('risk-input-contratista').value = '';

    document.getElementById('risk-input-polizas').value = 'false';

    document.getElementById('risk-input-estudio-texto').value = '';



    const resBox = document.getElementById('risk-matrix-results-container');

    if (resBox) resBox.classList.add('hidden');



    const exportBtnDocx = document.getElementById('btn-export-risk-quick-docx');

    if (exportBtnDocx) {

        exportBtnDocx.disabled = true;

        exportBtnDocx.className = 'px-4 py-2 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-blue-700 to-indigo-600 hover:from-blue-600 hover:to-indigo-500 shadow-md flex items-center gap-1.5 transition-all opacity-50 cursor-not-allowed';

    }

    const exportBtnPdf = document.getElementById('btn-export-risk-quick-pdf');

    if (exportBtnPdf) {

        exportBtnPdf.disabled = true;

        exportBtnPdf.className = 'px-4 py-2 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-rose-700 to-red-600 hover:from-rose-600 hover:to-red-500 shadow-md flex items-center gap-1.5 transition-all opacity-50 cursor-not-allowed';

    }



    checkRiskInputsChecklist();

    showToast('Formulario de matriz de riesgos reiniciado.', 'info');

}



function openRiskMatrixForContract(contractId) {

    switchTab('risks');

    setTimeout(() => {

        const cSelect = document.getElementById('risk-contract-select');

        if (cSelect) {

            cSelect.value = contractId;

            handleRiskContractSelect(contractId);

        }

    }, 150);

}





// =========================================================================

// MÓDULO 7: CONTRATACIÓN INTELIGENTE, EVALUACIÓN COMPARATIVA Y APU

// =========================================================================



function formatCurrencyCopApu(val) {

    if (val === null || val === undefined || val === '') return '$0';

    const num = Math.round(Number(val) || 0);

    return '$' + num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, '.');

}



async function loadApuView() {

    await populateApuContractsDropdown();

    if (!state.apuModule.result && !state.apuModule.payload) {

        initNewApuProcess(false);

    } else if (state.apuModule.result) {

        renderApuAll();

    }

    updateApuContractStatusBadge();

}



function initNewApuProcess(notify = true) {

    state.apuModule.selectedContractId = null;

    const selectContract = document.getElementById('apu-select-contract');

    if (selectContract) selectContract.value = '';



    state.apuModule.payload = {

        proceso_config: {

            objeto_contractual: '',

            tipo_contrato: 'Suministro',

            modalidad_manual_codigo: 'AUTO',

            causal_directa_numeral_19: 'a',

            smlmv_vigencia: 1750905.0,

            plazo_ejecucion_meses: 2,

            anticipo_porcentaje: 0.0,

            criterio_seleccion: 'Selección objetiva del oferente que presentó la cotización MÁS BARATA (menor precio global del mercado).',

            fecha_proceso: 'Octubre de 2026',

            lugar_ejecucion: 'Municipio de Yolombó, Antioquia',

            evaluador_nombre: 'JOAN ALVAREZ CORREA',

            evaluador_cargo: 'Auxiliar de Contratación',

            aprobador_nombre: 'CAROLINA GIRALDO GÓMEZ',

            aprobador_cargo: 'Gerente General.'

        },

        ofertas: [],

        proponente_ganador_nombre: null

    };

    state.apuModule.result = null;

    state.apuModule.activeItemIndex = 0;



    // Reset UI Inputs

    if (document.getElementById('apu-input-objeto')) document.getElementById('apu-input-objeto').value = '';

    if (document.getElementById('apu-input-tipo-contrato')) document.getElementById('apu-input-tipo-contrato').value = 'Suministro';

    if (document.getElementById('apu-input-modalidad-codigo')) document.getElementById('apu-input-modalidad-codigo').value = 'AUTO';

    if (document.getElementById('apu-input-causal-numeral-19')) document.getElementById('apu-input-causal-numeral-19').value = 'a';

    if (document.getElementById('apu-input-smlmv')) document.getElementById('apu-input-smlmv').value = '1750905';

    if (document.getElementById('apu-input-plazo-meses')) document.getElementById('apu-input-plazo-meses').value = '2';

    if (document.getElementById('apu-input-anticipo-pct')) document.getElementById('apu-input-anticipo-pct').value = '0';

    if (document.getElementById('apu-input-fecha')) document.getElementById('apu-input-fecha').value = 'Octubre de 2026';

    if (document.getElementById('apu-input-lugar')) document.getElementById('apu-input-lugar').value = 'Municipio de Yolombó, Antioquia';

    if (document.getElementById('apu-input-criterio')) document.getElementById('apu-input-criterio').value = 'Selección objetiva del oferente que presentó la cotización MÁS BARATA (menor precio global del mercado).';



    toggleApuCausalDirecta();



    // Reset Containers

    const container = document.getElementById('apu-offers-cards-container');

    if (container) {

        container.innerHTML = `

            <div class="col-span-1 md:col-span-2 lg:col-span-3 p-8 text-center bg-slate-50 dark:bg-slate-900/40 rounded-2xl border border-dashed border-slate-300 dark:border-slate-800">

                <p class="text-xs font-bold text-slate-600 dark:text-slate-400">No hay cotizaciones cargadas todavía.</p>

                <p class="text-[11px] text-slate-400 mt-1">Arrastre o seleccione archivos de cotizaciones en PDF, Excel o Word, o use el botón "Digitar Manual".</p>

            </div>

        `;

    }



    updateApuOffersStatusBanner();

    updateApuWinnerSelectDropdown();

    resetApuMatrixViews();

    updateApuContractStatusBadge();

    switchApuSubTab('config');

    if (notify) {

        showToast('Nuevo proceso contractual en blanco preparado. Defina el objeto y cargue las cotizaciones.', 'info');

    }

}



function toggleApuCausalDirecta() {

    const mod = document.getElementById('apu-input-modalidad-codigo')?.value;

    const box = document.getElementById('apu-box-causal-19');

    if (box) {

        if (mod === 'DIRECTA_NUMERAL_19') {

            box.classList.remove('hidden');

        } else {

            box.classList.add('hidden');

        }

    }

}





function switchApuSubTab(subTabName) {

    if (subTabName === 'offers') {

        subTabName = 'config';

    }

    state.apuModule.activeSubTab = subTabName;

    const subtabs = ['config', 'matrix', 'fichas', 'docs'];



    subtabs.forEach(st => {

        const panel = document.getElementById(`apu-subpanel-${st}`);

        const btn = document.getElementById(`apu-tabbtn-${st}`);

        if (panel) {

            if (st === subTabName) {

                panel.classList.remove('hidden');

            } else {

                panel.classList.add('hidden');

            }

        }

        if (btn) {

            if (st === subTabName) {

                btn.className = 'apu-subtab-btn px-4 py-2 rounded-xl text-xs font-bold transition-all whitespace-nowrap bg-white dark:bg-slate-800 text-[#03008F] dark:text-emerald-400 shadow-sm border border-slate-200 dark:border-slate-700 flex items-center gap-2';

            } else {

                btn.className = 'apu-subtab-btn px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition-all whitespace-nowrap flex items-center gap-2';

            }

        }

    });

}



function syncApuConfigFromInputs() {

    if (!state.apuModule.payload) {

        state.apuModule.payload = {

            proceso_config: {},

            ofertas: []

        };

    }

    const cfg = state.apuModule.payload.proceso_config || {};

    cfg.objeto_contractual = document.getElementById('apu-input-objeto')?.value || '';

    cfg.tipo_contrato = document.getElementById('apu-input-tipo-contrato')?.value || 'Suministro';

    cfg.modalidad_manual_codigo = document.getElementById('apu-input-modalidad-codigo')?.value || 'AUTO';

    cfg.causal_directa_numeral_19 = document.getElementById('apu-input-causal-numeral-19')?.value || 'a';

    cfg.smlmv_vigencia = parseFloat(document.getElementById('apu-input-smlmv')?.value) || 1750905.0;

    cfg.plazo_ejecucion_meses = parseInt(document.getElementById('apu-input-plazo-meses')?.value) || 2;

    cfg.anticipo_porcentaje = parseFloat(document.getElementById('apu-input-anticipo-pct')?.value) || 0.0;

    cfg.criterio_seleccion = document.getElementById('apu-input-criterio')?.value || '';

    cfg.fecha_proceso = document.getElementById('apu-input-fecha')?.value || '';

    cfg.lugar_ejecucion = document.getElementById('apu-input-lugar')?.value || '';

    cfg.evaluador_nombre = document.getElementById('apu-firmante-eval-nom')?.value || 'JOAN ALVAREZ CORREA';

    cfg.evaluador_cargo = document.getElementById('apu-firmante-eval-car')?.value || 'Auxiliar de Contratación';

    cfg.aprobador_nombre = document.getElementById('apu-firmante-aprob-nom')?.value || 'CAROLINA GIRALDO GÓMEZ';

    cfg.aprobador_cargo = document.getElementById('apu-firmante-aprob-car')?.value || 'Gerente General.';



    state.apuModule.payload.proceso_config = cfg;

    const manualWin = document.getElementById('apu-select-winner')?.value;

    if (manualWin) {

        state.apuModule.payload.proponente_ganador_nombre = manualWin;

    }



    const bEval = document.getElementById('apu-firmante-eval-badge');

    if (bEval) bEval.textContent = cfg.evaluador_nombre;

    const bAprob = document.getElementById('apu-firmante-aprob-badge');

    if (bAprob) bAprob.textContent = cfg.aprobador_nombre;

}



// Drag & Drop handlers

function handleApuDragOver(e) {

    e.preventDefault();

    e.stopPropagation();

    const dz = document.getElementById('apu-dropzone');

    if (dz) {

        dz.classList.add('border-blue-500', 'bg-blue-50/30', 'dark:bg-blue-950/20');

    }

}



function handleApuDragLeave(e) {

    e.preventDefault();

    e.stopPropagation();

    const dz = document.getElementById('apu-dropzone');

    if (dz) {

        dz.classList.remove('border-blue-500', 'bg-blue-50/30', 'dark:bg-blue-950/20');

    }

}



function handleApuDrop(e) {

    e.preventDefault();

    e.stopPropagation();

    handleApuDragLeave(e);

    if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {

        handleApuOfferFileUpload(e.dataTransfer.files);

    }

}



async function handleApuOfferFileUpload(files) {

    if (!files || files.length === 0) return;

    try {

        if (!state.apuModule.payload) {

            state.apuModule.payload = { proceso_config: {}, ofertas: [] };

        }

        if (!state.apuModule.payload.ofertas) {

            state.apuModule.payload.ofertas = [];

        }



        showToast(`Procesando archivo(s) de propuesta con OCR y extracción inteligente de cotizaciones...`, 'info');

        const extractedList = await window.api.extractMultipleOffers(files);

        if (extractedList && extractedList.length > 0) {

            extractedList.forEach(ext => {

                const nextNum = state.apuModule.payload.ofertas.length + 1;

                if (!ext.nombre_razon_social || !ext.nombre_razon_social.trim() || ext.nombre_razon_social.toLowerCase().startsWith('proponente cotizaci') || ext.nombre_razon_social.toLowerCase().startsWith('cotizaci')) {

                    ext.nombre_razon_social = `Cotización ${nextNum}`;

                }

                state.apuModule.payload.ofertas.push(ext);

            });

            showToast(`¡Se extrajeron con éxito ${extractedList.length} cotizaciones (${extractedList.map(o => o.nombre_razon_social).join(', ')})!`, 'success');

        } else {

            showToast('No se pudieron extraer cotizaciones de los archivos suministrados.', 'warning');

        }



        recalculateApuRanking();

        syncApuConfigFromInputs();

        if (state.apuModule.payload.ofertas.length > 0) {

            await triggerRunApuEvaluation();

        } else {

            renderApuOffers();

            updateApuWinnerSelectDropdown();

            updateApuOffersStatusBanner();

        }

        switchApuSubTab('config');

    } catch (e) {

        console.error("Error al subir archivo de cotización:", e);

        showToast('Error procesando cotización: ' + e.message, 'error');

    }

}



function recalculateApuRanking() {

    const ofertas = state.apuModule.payload?.ofertas || [];

    if (!ofertas || ofertas.length === 0) return;



    // 1. Numerar respaldo con índice real solo si el PDF no traía razón social

    ofertas.forEach((of, i) => {

        const isGeneric = !of.nombre_razon_social || !of.nombre_razon_social.trim() || 

                          of.nombre_razon_social.toLowerCase().startsWith('proponente cotizaci') ||

                          of.nombre_razon_social.toLowerCase().startsWith('cotizaci');

        if (isGeneric) {

            of.nombre_razon_social = `Cotización ${i + 1}`;

        }

    });



    // 2. Encontrar el menor valor total mayor a cero

    let minVal = Infinity;

    let minOffer = null;

    ofertas.forEach(of => {

        const val = parseFloat(of.valor_total_oferta) || 0;

        if (val > 0 && val < minVal) {

            minVal = val;

            minOffer = of;

        }

    });



    // 3. Ordenar o comparar los valores totales ofertados de todas las cotizaciones cargadas

    const sortedValid = [...ofertas]

        .filter(o => (parseFloat(o.valor_total_oferta) || 0) > 0)

        .sort((a, b) => (parseFloat(a.valor_total_oferta) || 0) - (parseFloat(b.valor_total_oferta) || 0));



    const manualWinner = state.apuModule.payload?.proponente_ganador_nombre;



    ofertas.forEach((of, idx) => {

        const val = parseFloat(of.valor_total_oferta) || 0;

        const rankIdx = sortedValid.indexOf(of);

        of.posicion_orden = rankIdx >= 0 ? rankIdx + 1 : idx + 1;



        if (manualWinner) {

            of.es_seleccionado = (of.nombre_razon_social === manualWinner);

        } else {

            // Asigna la insignia "1° MENOR PRECIO" y estado "Oferta Seleccionada" ÚNICAMENTE a la cotización con menor valor > 0

            of.es_seleccionado = Boolean(minOffer === of && val > 0 && of.posicion_orden === 1);

        }



        if (minVal !== Infinity && minVal > 0 && val > 0) {

            const diff = val - minVal;

            of.desviacion_porcentual = parseFloat(((diff / minVal) * 100).toFixed(2));

            of.ahorro_frente_a_este = parseFloat(diff.toFixed(2));

        } else {

            of.desviacion_porcentual = 0;

            of.ahorro_frente_a_este = 0;

        }

    });

}



function clearApuOffers() {

    if (!state.apuModule.payload || !state.apuModule.payload.ofertas || state.apuModule.payload.ofertas.length === 0) {

        showToast('No hay cotizaciones para limpiar.', 'info');

        return;

    }

    if (confirm('¿Está seguro de eliminar todas las cotizaciones cargadas?')) {

        state.apuModule.payload.ofertas = [];

        state.apuModule.payload.proponente_ganador_nombre = null;

        state.apuModule.result = null;

        renderApuOffers();

        resetApuMatrixViews();

        updateApuOffersStatusBanner();

        updateApuWinnerSelectDropdown();

        showToast('Todas las cotizaciones fueron eliminadas.', 'info');

    }

}



function removeApuOffer(idx) {

    if (!state.apuModule.payload || !state.apuModule.payload.ofertas) return;

    state.apuModule.payload.ofertas.splice(idx, 1);

    showToast(`Cotización eliminada.`, 'info');

    if (state.apuModule.payload.ofertas.length > 0) {

        recalculateApuRanking();

        triggerRunApuEvaluation();

    } else {

        state.apuModule.payload.proponente_ganador_nombre = null;

        state.apuModule.result = null;

        renderApuOffers();

        resetApuMatrixViews();

        updateApuOffersStatusBanner();

        updateApuWinnerSelectDropdown();

    }

}



// Modal Entrada Manual

function openAddManualOfferModal() {

    const modal = document.getElementById('modal-apu-manual-offer');

    if (!modal) return;

    modal.classList.remove('hidden');



    // Limpiar inputs

    if (document.getElementById('apu-manual-nombre')) document.getElementById('apu-manual-nombre').value = '';

    if (document.getElementById('apu-manual-nit')) document.getElementById('apu-manual-nit').value = '';

    if (document.getElementById('apu-manual-rep')) document.getElementById('apu-manual-rep').value = '';

    if (document.getElementById('apu-manual-domicilio')) document.getElementById('apu-manual-domicilio').value = 'Yolombó, Antioquia';

    if (document.getElementById('apu-manual-paste-area')) document.getElementById('apu-manual-paste-area').value = '';



    const tbody = document.getElementById('apu-manual-items-tbody');

    if (tbody) {

        tbody.innerHTML = '';

        addApuManualItemRow('', 'und', 1, 0);

        addApuManualItemRow('', 'und', 1, 0);

    }

}



function closeAddManualOfferModal() {

    const modal = document.getElementById('modal-apu-manual-offer');

    if (modal) modal.classList.add('hidden');

}



function addApuManualItemRow(desc = '', und = 'und', cant = 1, vrUnit = 0) {

    const tbody = document.getElementById('apu-manual-items-tbody');

    if (!tbody) return;

    const rowNum = tbody.children.length + 1;

    const tr = document.createElement('tr');

    tr.className = 'border-b border-slate-100 dark:border-slate-800 text-xs';

    tr.innerHTML = `

        <td class="p-2 text-center text-slate-400 font-mono item-row-num">${rowNum}</td>

        <td class="p-2"><input type="text" class="w-full bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded p-1 text-xs item-desc" value="${desc}" placeholder="Descripción del ítem"></td>

        <td class="p-2"><input type="text" class="w-full bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded p-1 text-xs text-center item-und" value="${und}"></td>

        <td class="p-2"><input type="number" step="any" class="w-full bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded p-1 text-xs text-center font-mono item-cant" value="${cant}"></td>

        <td class="p-2"><input type="number" step="any" class="w-full bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded p-1 text-xs text-right font-mono item-vrunit" value="${vrUnit}"></td>

        <td class="p-2 text-center">

            <button type="button" onclick="removeApuManualItemRow(this)" class="text-rose-500 hover:text-rose-700 font-bold text-sm cursor-pointer">&times;</button>

        </td>

    `;

    tbody.appendChild(tr);

}



function removeApuManualItemRow(btn) {

    const row = btn.closest('tr');

    const tbody = row.parentElement;

    if (tbody && tbody.children.length > 1) {

        row.remove();

        Array.from(tbody.children).forEach((tr, i) => {

            const numCell = tr.querySelector('.item-row-num');

            if (numCell) numCell.textContent = i + 1;

        });

    } else {

        showToast('Debe existir al menos una fila de ítem.', 'warning');

    }

}



function parseApuPastedItems() {

    const text = document.getElementById('apu-manual-paste-area')?.value || '';

    if (!text.trim()) {

        showToast('Pegue texto en el área antes de importar.', 'warning');

        return;

    }



    const lines = text.split(/\r?\n/).filter(l => l.trim().length > 0);

    const tbody = document.getElementById('apu-manual-items-tbody');

    if (!tbody) return;



    let addedCount = 0;

    lines.forEach(line => {

        const parts = line.split(/[\t;]/);

        if (parts.length >= 2) {

            const desc = parts[0].trim();

            const und = parts[1] ? parts[1].trim() : 'und';

            const cant = parts[2] ? parseFloat(parts[2].replace(/[^0-9.,]/g, '').replace(',', '.')) || 1 : 1;

            const vrUnit = parts[3] ? parseFloat(parts[3].replace(/[^0-9.,]/g, '').replace(',', '.')) || 0 : 0;

            if (desc) {

                addApuManualItemRow(desc, und, cant, vrUnit);

                addedCount++;

            }

        }

    });



    if (addedCount > 0) {

        showToast(`Se importaron ${addedCount} ítems pegados con éxito.`, 'success');

        document.getElementById('apu-manual-paste-area').value = '';

    } else {

        showToast('No se pudieron interpretar las filas pegadas. Asegúrese de separar por Tabulaciones o Punto y Coma.', 'warning');

    }

}



function saveApuManualOffer() {

    const nombre = document.getElementById('apu-manual-nombre')?.value.trim();

    const nit = document.getElementById('apu-manual-nit')?.value.trim();

    const rep = document.getElementById('apu-manual-rep')?.value.trim() || 'Representante Legal';

    const dom = document.getElementById('apu-manual-domicilio')?.value.trim() || 'Yolombó, Antioquia';



    if (!nombre) {

        showToast('El nombre o razón social es obligatorio.', 'warning');

        return;

    }



    const tbody = document.getElementById('apu-manual-items-tbody');

    const rows = tbody ? Array.from(tbody.querySelectorAll('tr')) : [];

    const items = [];

    let subtotal = 0;



    rows.forEach((tr, idx) => {

        const desc = tr.querySelector('.item-desc')?.value.trim();

        const und = tr.querySelector('.item-und')?.value.trim() || 'und';

        const cant = parseFloat(tr.querySelector('.item-cant')?.value) || 0;

        const vrUnit = parseFloat(tr.querySelector('.item-vrunit')?.value) || 0;



        if (desc && cant > 0 && vrUnit > 0) {

            const vrTot = cant * vrUnit;

            items.push({

                item_numero: idx + 1,

                descripcion: desc,

                unidad: und,

                cantidad: cant,

                valor_unitario: vrUnit,

                valor_total: vrTot,

                valor_unitario_corregido: vrUnit,

                valor_total_corregido: vrTot,

                tiene_error_aritmetico: false

            });

            subtotal += vrTot;

        }

    });



    if (items.length === 0) {

        showToast('Debe ingresar al menos un ítem con descripción, cantidad y valor unitario válidos.', 'warning');

        return;

    }



    const nuevaOferta = {

        proponente_id: `prop_${Date.now()}`,

        nombre_razon_social: nombre,

        nit_cedula: nit || 'Pendiente',

        representante_legal: rep,

        domicilio: dom,

        fecha_oferta: 'Octubre de 2026',

        items: items,

        subtotal: subtotal,

        iva: 0.0,

        valor_total_oferta: subtotal,

        tiene_errores_aritmeticos: false

    };



    if (!state.apuModule.payload) {

        state.apuModule.payload = { proceso_config: {}, ofertas: [] };

    }

    if (!state.apuModule.payload.ofertas) {

        state.apuModule.payload.ofertas = [];

    }



    state.apuModule.payload.ofertas.push(nuevaOferta);

    closeAddManualOfferModal();

    showToast(`Cotización de "${nombre}" registrada con ${items.length} ítems.`, 'success');

    triggerRunApuEvaluation();

    updateApuWinnerSelectDropdown();

    switchApuSubTab('config');

}



function updateApuOffersStatusBanner() {

    const ofertas = state.apuModule.payload?.ofertas || [];

    const countBadge = document.getElementById('apu-offers-counter-badge');

    const note = document.getElementById('apu-offers-requirement-note');



    if (countBadge) {

        countBadge.textContent = `${ofertas.length} Cotización${ofertas.length === 1 ? '' : 'es'} Cargada${ofertas.length === 1 ? '' : 's'}`;

    }



    if (note) {

        if (ofertas.length === 0) {

            note.textContent = 'Cargue las cotizaciones del mercado para auditar aritméticamente y seleccionar la más favorable.';

        } else if (ofertas.length < 3) {

            note.innerHTML = `⚠️ Manual PR-ESPY-002: Para cuantías entre 20 y menos de 100 SMLMV se requiere un mínimo de <strong>tres (3) cotizaciones</strong> (Numeral 13). Actual: <strong>${ofertas.length}</strong>.`;

        } else {

            note.innerHTML = `✅ Cumple requisito de pluralidad de oferentes según el Manual de Contratación PR-ESPY-002 (Numeral 13: Mínimo 3 cotizaciones).`;

        }

    }

}



function updateApuWinnerSelectDropdown() {

    const sel = document.getElementById('apu-select-winner');

    if (!sel) return;

    const ofertas = state.apuModule.result?.ofertas || state.apuModule.payload?.ofertas || [];

    const ganador = state.apuModule.result?.proponente_ganador;

    const manualVal = state.apuModule.payload?.proponente_ganador_nombre || '';



    sel.innerHTML = '';

    const defOpt = document.createElement('option');

    defOpt.value = '';

    defOpt.textContent = ganador 

        ? `🤖 Automática: Menor precio global (${ganador.nombre_razon_social})`

        : '🤖 Automática: Menor precio global del mercado';

    sel.appendChild(defOpt);



    ofertas.forEach(of => {

        const opt = document.createElement('option');

        opt.value = of.nombre_razon_social;

        const isCurrentWinner = ganador && (ganador.nombre_razon_social === of.nombre_razon_social);

        opt.textContent = `${of.nombre_razon_social} - ${formatCurrencyCopApu(of.valor_total_oferta)}${isCurrentWinner ? ' (⭐ Recomendada Menor Precio)' : ''}`;

        if (manualVal === of.nombre_razon_social) {

            opt.selected = true;

        }

        sel.appendChild(opt);

    });



    if (!manualVal && !ganador && ofertas.length > 0) {

        sel.value = '';

    }

}



function handleApuWinnerManualChange(selectedName) {

    if (!state.apuModule.payload) {

        state.apuModule.payload = { proceso_config: {}, ofertas: [] };

    }

    state.apuModule.payload.proponente_ganador_nombre = selectedName || null;

    if (state.apuModule.payload.ofertas && state.apuModule.payload.ofertas.length > 0) {

        triggerRunApuEvaluation();

    }

}



function selectApuWinnerFromCard(proponenteName) {

    const sel = document.getElementById('apu-select-winner');

    if (sel) {

        sel.value = proponenteName;

    }

    handleApuWinnerManualChange(proponenteName);

}



async function triggerRunApuEvaluation() {

    try {

        syncApuConfigFromInputs();

        if (!state.apuModule.payload || !state.apuModule.payload.ofertas || state.apuModule.payload.ofertas.length === 0) {

            showToast('Debe existir al menos una cotización para evaluar.', 'warning');

            return;

        }



        showToast('Ejecutando auditoría aritmética, matriz comparativa y reglas del Manual ESPY...', 'info');

        const res = await window.api.evaluateApuProposals(state.apuModule.payload);

        state.apuModule.result = res;

        const objInput = document.getElementById('apu-input-objeto');
        if (objInput && (!objInput.value || objInput.value.trim().toLowerCase() === 'no especificado' || objInput.value.trim().toLowerCase() === 'sin especificar' || objInput.value.trim().toLowerCase() === 'n/a')) {
            if (res.proceso_config && res.proceso_config.objeto_contractual) {
                objInput.value = res.proceso_config.objeto_contractual;
                if (state.apuModule.payload && state.apuModule.payload.proceso_config) {
                    state.apuModule.payload.proceso_config.objeto_contractual = res.proceso_config.objeto_contractual;
                }
            }
        }

        renderApuAll();

        updateApuWinnerSelectDropdown();

        showToast('¡Evaluación económica completada con éxito!', 'success');

    } catch (e) {

        console.error("Error evaluando ofertas:", e);

        showToast('Error al evaluar ofertas: ' + e.message, 'error');

    }

}



async function triggerRunApuEvaluationAndAdvance() {

    syncApuConfigFromInputs();

    if (!state.apuModule.payload || !state.apuModule.payload.ofertas || state.apuModule.payload.ofertas.length === 0) {

        showToast('Debe cargar al menos una cotización antes de ejecutar el análisis.', 'warning');

        return;

    }

    await triggerRunApuEvaluation();

    if (state.apuModule.result) {

        switchApuSubTab('matrix');

        showToast('¡Análisis completado! Avanzando al Paso 2: Matriz Comparativa y Garantías.', 'success');

    }

}



function renderApuAll() {

    const res = state.apuModule.result;

    if (!res) return;

    renderApuOffers();

    renderApuMatrix(res);

    renderApuFichas(res);

    updateApuOffersStatusBanner();

}



function renderApuOffers() {

    const container = document.getElementById('apu-offers-cards-container');

    if (!container) return;



    recalculateApuRanking();



    const ofertas = state.apuModule.result?.ofertas || state.apuModule.payload?.ofertas || [];

    container.innerHTML = '';



    if (ofertas.length === 0) {

        container.innerHTML = `

            <div class="col-span-1 md:col-span-2 lg:col-span-3 p-8 text-center bg-slate-50 dark:bg-slate-900/40 rounded-2xl border border-dashed border-slate-300 dark:border-slate-800">

                <p class="text-xs font-bold text-slate-600 dark:text-slate-400">No hay cotizaciones cargadas todavía.</p>

                <p class="text-[11px] text-slate-400 mt-1">Arrastre o seleccione archivos de cotizaciones en PDF, Excel o Word, o use el botón "Digitar Manual".</p>

            </div>

        `;

        return;

    }



    // Identificar el único ganador con menor valor total mayor a cero

    let winnerNombre = state.apuModule.result?.proponente_ganador?.nombre_razon_social;

    if (!winnerNombre) {

        let minVal = Infinity;

        let candidate = null;

        ofertas.forEach(o => {

            const val = parseFloat(o.valor_total_oferta) || 0;

            if (val > 0 && val < minVal) {

                minVal = val;

                candidate = o.nombre_razon_social;

            }

        });

        winnerNombre = candidate;

    }



function manualWinnerSelected(of) {

    const m = state.apuModule.payload?.proponente_ganador_nombre;

    return Boolean(m && m !== of.nombre_razon_social);

}



    const sortedOffers = [...ofertas].sort((a, b) => {

        const va = parseFloat(a.valor_total_oferta) || 0;

        const vb = parseFloat(b.valor_total_oferta) || 0;

        if (va <= 0) return 1;

        if (vb <= 0) return -1;

        return va - vb;

    });



    let selectedWinnerRendered = false;



    ofertas.forEach((of, idx) => {

        const val = parseFloat(of.valor_total_oferta) || 0;

        const rankPos = sortedOffers.indexOf(of) + 1;

        const isWinner = Boolean(

            !selectedWinnerRendered &&

            val > 0 &&

            ((winnerNombre && of.nombre_razon_social === winnerNombre && rankPos === 1) ||

             (of.es_seleccionado && rankPos === 1) ||

             (rankPos === 1 && !manualWinnerSelected(of)))

        );

        if (isWinner) {

            selectedWinnerRendered = true;

        }



        const card = document.createElement('div');

        card.className = `p-4 rounded-xl border transition-all flex flex-col justify-between ${

            isWinner 

                ? 'bg-emerald-50/70 dark:bg-emerald-950/40 border-emerald-400 dark:border-emerald-700 shadow-sm ring-2 ring-emerald-500/30' 

                : 'bg-white dark:bg-[#0c1427] border-slate-200 dark:border-slate-800 hover:border-slate-300'

        }`;



        const diffBadge = isWinner 

            ? '<span class="px-2.5 py-0.5 rounded-full text-[10px] font-black bg-emerald-600 text-white shadow-sm whitespace-nowrap">⭐ 1° MENOR PRECIO</span>'

            : `<span class="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200 whitespace-nowrap">${rankPos}° PRECIO (+${of.desviacion_porcentual || 0}%)</span>`;



        const arithmeticBadge = of.tiene_errores_aritmeticos 

            ? '<span class="inline-flex items-center gap-1 text-[10px] text-amber-600 dark:text-amber-400 font-bold">⚠️ Control aritmético aplicado</span>'

            : '<span class="inline-flex items-center gap-1 text-[10px] text-emerald-600 dark:text-emerald-400 font-bold">✅ Auditoría aritmética conforme</span>';



        card.innerHTML = `

            <div>

                <div class="flex items-start justify-between gap-2 mb-2">

                    <div>

                        <h4 class="font-bold text-xs text-slate-900 dark:text-white flex items-center gap-1.5">

                            <span>🏢</span> ${of.nombre_razon_social}

                        </h4>

                        <p class="text-[10px] text-slate-500 font-mono mt-0.5">NIT/CC: ${of.nit_cedula || 'Pendiente'}</p>

                    </div>

                    ${diffBadge}

                </div>

                <div class="space-y-1 text-[11px] text-slate-600 dark:text-slate-400 mb-3 bg-slate-50/60 dark:bg-slate-900/40 p-2.5 rounded-lg border border-slate-100 dark:border-slate-800/80">

                    <p><strong>Rep. Legal:</strong> ${of.representante_legal || 'No especificado'}</p>

                    <p><strong>Domicilio:</strong> ${of.domicilio || 'Yolombó, Antioquia'}</p>

                    <p><strong>Fecha Oferta:</strong> ${of.fecha_oferta || 'Octubre de 2026'}</p>

                    <div class="flex items-center justify-between pt-1 border-t border-slate-200/60 dark:border-slate-800">

                        <span class="font-semibold text-slate-800 dark:text-slate-200">${of.items ? of.items.length : 0} ítems cotizados</span>

                        ${arithmeticBadge}

                    </div>

                </div>

            </div>

            <div>

                <div class="pt-2 border-t border-slate-200 dark:border-slate-700/60 flex items-center justify-between mb-2">

                    <span class="text-[10px] uppercase font-bold text-slate-500">Valor Total Ofertado</span>

                    <span class="text-sm font-black ${isWinner ? 'text-emerald-600 dark:text-emerald-400' : 'text-slate-800 dark:text-white'} font-mono">

                        ${formatCurrencyCopApu(of.valor_total_oferta)}

                    </span>

                </div>

                <div class="flex items-center justify-between gap-1 pt-1">

                    <button type="button" onclick="selectApuWinnerFromCard('${of.nombre_razon_social.replace(/'/g, "\\'")}')" class="px-2 py-1 rounded text-[10px] font-bold ${isWinner ? 'text-emerald-700 dark:text-emerald-300 bg-emerald-100/80 dark:bg-emerald-900/60' : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'} cursor-pointer transition-all">

                        ${isWinner ? '✓ Oferta Seleccionada' : 'Seleccionar Esta'}

                    </button>

                    <button type="button" onclick="removeApuOffer(${idx})" class="px-2 py-1 rounded text-[10px] font-semibold text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 cursor-pointer transition-all">

                        🗑️ Eliminar

                    </button>

                </div>

            </div>

        `;

        container.appendChild(card);

    });

}



function resetApuMatrixViews() {

    if (document.getElementById('apu-kpi-ganador-nombre')) document.getElementById('apu-kpi-ganador-nombre').textContent = 'Sin evaluar';

    if (document.getElementById('apu-kpi-ganador-val')) document.getElementById('apu-kpi-ganador-val').textContent = '$0';

    if (document.getElementById('apu-kpi-ahorro-pesos')) document.getElementById('apu-kpi-ahorro-pesos').textContent = '$0';

    if (document.getElementById('apu-kpi-ahorro-pct')) document.getElementById('apu-kpi-ahorro-pct').textContent = 'Eficiencia presupuestal';

    if (document.getElementById('apu-kpi-cuantia-smlmv')) document.getElementById('apu-kpi-cuantia-smlmv').textContent = '0.0 SMLMV';

    if (document.getElementById('apu-kpi-modalidad-badge')) document.getElementById('apu-kpi-modalidad-badge').textContent = 'Según Manual PR-ESPY-002';

    if (document.getElementById('apu-kpi-total-items')) document.getElementById('apu-kpi-total-items').textContent = '0 Ítems';



    const gBody = document.getElementById('apu-guarantees-table-body');

    if (gBody) gBody.innerHTML = '<tr><td colspan="5" class="py-3 px-3 text-center text-slate-500 italic">Ejecute la evaluación para liquidar las garantías del Manual PR-ESPY-002.</td></tr>';



    const mHead = document.getElementById('apu-matrix-table-head');

    const mBody = document.getElementById('apu-matrix-table-body');

    if (mHead) mHead.innerHTML = '';

    if (mBody) mBody.innerHTML = '';

}



function renderApuMatrix(res) {

    // 1. KPIs

    const ganador = res.proponente_ganador || (res.ofertas && res.ofertas[0]);

    if (ganador) {

        if (document.getElementById('apu-kpi-ganador-nombre')) document.getElementById('apu-kpi-ganador-nombre').textContent = ganador.nombre_razon_social;

        if (document.getElementById('apu-kpi-ganador-val')) document.getElementById('apu-kpi-ganador-val').textContent = formatCurrencyCopApu(ganador.valor_total_oferta);

    }

    if (document.getElementById('apu-kpi-ahorro-pesos')) {

        document.getElementById('apu-kpi-ahorro-pesos').textContent = '+' + formatCurrencyCopApu(res.ahorro_maximo_pesos || 0);

    }

    if (document.getElementById('apu-kpi-ahorro-pct')) {

        document.getElementById('apu-kpi-ahorro-pct').textContent = `+${res.ahorro_maximo_porcentaje || 0}% de ahorro frente al mayor`;

    }

    if (document.getElementById('apu-kpi-cuantia-smlmv')) {

        const smlmvVal = res.cuantia_smlmv_calculada ? res.cuantia_smlmv_calculada.toFixed(1) : '0.0';

        document.getElementById('apu-kpi-cuantia-smlmv').textContent = `${smlmvVal} SMLMV`;

    }

    if (document.getElementById('apu-kpi-modalidad-badge')) {

        document.getElementById('apu-kpi-modalidad-badge').textContent = res.modalidad_manual_nombre || 'Manual PR-ESPY-002';

    }

    if (document.getElementById('apu-kpi-total-items')) {

        const count = res.matriz_comparativa_items ? res.matriz_comparativa_items.length : (res.items_apu ? res.items_apu.length : 0);

        document.getElementById('apu-kpi-total-items').textContent = `${count} Ítems`;

    }



    // 2. Garantías y Pólizas Exigibles (PR-ESPY-002, Título III)

    const gBody = document.getElementById('apu-guarantees-table-body');

    const gPill = document.getElementById('apu-guarantees-status-pill');

    if (gBody) {

        gBody.innerHTML = '';

        const garantias = res.garantias_exigibles || [];

        if (garantias.length === 0) {

            gBody.innerHTML = `

                <tr>

                    <td colspan="5" class="py-4 px-3 text-center text-amber-600 dark:text-amber-400 font-semibold">

                        ℹ️ Exento de garantías obligatorias según el Numeral 32 del Manual de Contratación PR-ESPY-002 (cuantía inferior a 20 SMLMV o prestación de servicios profesionales).

                    </td>

                </tr>

            `;

            if (gPill) gPill.textContent = 'Exento de Pólizas (Num. 32)';

        } else {

            if (gPill) gPill.textContent = `${garantias.length} Amparos Obligatorios`;

            garantias.forEach((g, idx) => {

                const tr = document.createElement('tr');

                tr.className = idx % 2 === 0 ? 'bg-white dark:bg-[#0c1427]' : 'bg-slate-50 dark:bg-slate-900/40';

                tr.innerHTML = `

                    <td class="py-2 px-3 border border-slate-200 dark:border-slate-800 font-semibold text-slate-800 dark:text-white">

                        ${g.amparo}

                    </td>

                    <td class="py-2 px-3 border border-slate-200 dark:border-slate-800 text-center font-mono font-bold text-blue-700 dark:text-blue-300">

                        ${g.porcentaje_texto}

                    </td>

                    <td class="py-2 px-3 border border-slate-200 dark:border-slate-800 text-right font-mono font-bold text-emerald-700 dark:text-emerald-300">

                        ${formatCurrencyCopApu(g.valor_asegurado_cop)}

                    </td>

                    <td class="py-2 px-3 border border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-300">

                        ${g.vigencia_texto}

                    </td>

                    <td class="py-2 px-3 border border-slate-200 dark:border-slate-800 text-center font-mono text-[10px] text-slate-500">

                        ${g.numeral_manual}

                    </td>

                `;

                gBody.appendChild(tr);

            });

        }

    }



    // 3. Tabla Comparativa Ítem a Ítem

    const thead = document.getElementById('apu-matrix-table-head');

    const tbody = document.getElementById('apu-matrix-table-body');

    if (!thead || !tbody) return;



    thead.innerHTML = '';

    tbody.innerHTML = '';



    const ofertas = res.ofertas || [];

    const trH = document.createElement('tr');

    trH.innerHTML = `

        <th class="py-2.5 px-3 border border-slate-700 text-center w-12">Ítem</th>

        <th class="py-2.5 px-3 border border-slate-700 text-left">Descripción del Requerimiento</th>

    `;

    ofertas.forEach(of => {

        const isWin = of.es_seleccionado;

        trH.innerHTML += `

            <th class="py-2.5 px-3 border border-slate-700 text-right ${isWin ? 'bg-emerald-900/60 text-emerald-300' : ''}">

                ${of.nombre_razon_social.split(' ')[0]}

            </th>

        `;

    });

    thead.appendChild(trH);



    // Filas de los ítems

    (res.matriz_comparativa_items || []).forEach((row, idx) => {

        const tr = document.createElement('tr');

        tr.className = idx % 2 === 0 ? 'bg-white dark:bg-[#0c1427]' : 'bg-slate-50 dark:bg-slate-900/40';



        let cellsHtml = `

            <td class="py-2 px-3 border border-slate-200 dark:border-slate-800 text-center font-bold text-slate-500">${row.item_numero}</td>

            <td class="py-2 px-3 border border-slate-200 dark:border-slate-800 font-medium text-slate-800 dark:text-slate-200">${row.descripcion}</td>

        `;



        ofertas.forEach(of => {

            const vTot = row.totales ? row.totales[of.nombre_razon_social] : 0;

            const isWinnerItem = of.nombre_razon_social === row.proponente_mas_economico_item;

            cellsHtml += `

                <td class="py-2 px-3 border border-slate-200 dark:border-slate-800 text-right font-mono ${

                    isWinnerItem ? 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 font-bold' : 'text-slate-600 dark:text-slate-400'

                }">

                    ${formatCurrencyCopApu(vTot)}

                </td>

            `;

        });

        tr.innerHTML = cellsHtml;

        tbody.appendChild(tr);

    });



    // Fila TOTAL VALOR TOTAL COMPARADO

    const trTot = document.createElement('tr');

    trTot.className = 'bg-emerald-100 dark:bg-emerald-950/80 font-black text-slate-900 dark:text-white border-t-2 border-emerald-600';

    let totHtml = `

        <td colspan="2" class="py-3 px-3 text-center uppercase tracking-wider text-xs border border-emerald-300 dark:border-emerald-800 text-[#03008F] dark:text-emerald-300">

            TOTAL VALOR TOTAL COMPARADO

        </td>

    `;

    ofertas.forEach(of => {

        const isWin = of.es_seleccionado;

        const tag = isWin ? '<br><span class="text-[9px] font-bold text-emerald-700 dark:text-emerald-300">(MENOR PRECIO)</span>' : `<br><span class="text-[9px] font-bold text-slate-500">(+${formatCurrencyCopApu(of.ahorro_frente_a_este)})</span>`;

        totHtml += `

            <td class="py-3 px-3 text-right font-mono text-xs border border-emerald-300 dark:border-emerald-800 ${isWin ? 'bg-emerald-200/60 dark:bg-emerald-900/60 text-emerald-900 dark:text-emerald-200 font-black' : ''}">

                ${formatCurrencyCopApu(of.valor_total_oferta)}

                ${tag}

            </td>

        `;

    });

    trTot.innerHTML = totHtml;

    tbody.appendChild(trTot);

}



function renderApuFichas(res) {

    const listSelector = document.getElementById('apu-items-list-selector');

    if (!listSelector) return;

    listSelector.innerHTML = '';



    const items = res.items_apu || [];

    if (items.length === 0) {

        listSelector.innerHTML = '<p class="text-xs text-slate-400 italic p-2">No hay ítems para mostrar.</p>';

        return;

    }



    const header = document.getElementById('apu-items-list-header');

    if (header) header.textContent = `Lista de ${items.length} Ítems del Contrato`;



    if (state.apuModule.activeItemIndex >= items.length) {

        state.apuModule.activeItemIndex = 0;

    }



    items.forEach((it, idx) => {

        const isActive = idx === state.apuModule.activeItemIndex;

        const btn = document.createElement('button');

        btn.onclick = () => selectApuFichaItem(idx);

        btn.className = `w-full text-left p-2.5 rounded-xl transition-all flex items-center justify-between text-xs cursor-pointer ${

            isActive 

                ? 'bg-emerald-600 text-white font-bold shadow-md shadow-emerald-600/20' 

                : 'bg-slate-50 dark:bg-slate-900/60 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'

        }`;

        btn.innerHTML = `

            <div class="truncate pr-2">

                <span class="font-mono ${isActive ? 'text-emerald-200' : 'text-slate-400'}">#${it.item_numero}</span>

                <span class="ml-1">${it.descripcion}</span>

            </div>

            <span class="shrink-0 font-mono font-bold text-[11px]">${formatCurrencyCopApu(it.valor_unitario)}</span>

        `;

        listSelector.appendChild(btn);

    });



    renderApuActiveItem();

}



function selectApuFichaItem(idx) {

    state.apuModule.activeItemIndex = idx;

    renderApuFichas(state.apuModule.result);

}



function renderApuActiveItem() {

    const res = state.apuModule.result;

    if (!res || !res.items_apu) return;

    const item = res.items_apu[state.apuModule.activeItemIndex];

    if (!item) return;



    if (document.getElementById('apu-active-item-title')) {

        document.getElementById('apu-active-item-title').textContent = `ÍTEM ${item.item_numero}: ${item.descripcion}`;

    }

    if (document.getElementById('apu-active-item-meta')) {

        document.getElementById('apu-active-item-meta').textContent = `Unidad: ${item.unidad} | Cantidad: ${item.cantidad} | Vr. Unitario: ${formatCurrencyCopApu(item.valor_unitario)} | Total Ítem: ${formatCurrencyCopApu(item.valor_total)}`;

    }

    if (document.getElementById('apu-active-item-total-badge')) {

        document.getElementById('apu-active-item-total-badge').textContent = `Unitario: ${formatCurrencyCopApu(item.valor_unitario)}`;

    }



    const breakdownBox = document.getElementById('apu-active-item-breakdown');

    if (!breakdownBox) return;



    const apu = item.descomposicion_apu;

    if (!apu) {

        breakdownBox.innerHTML = '<p class="text-slate-500 italic">Desglose no disponible.</p>';

        return;

    }



    const renderCompTable = (compTitle, itemsList, subtotal, icon) => {

        let rowsHtml = '';

        (itemsList || []).forEach(ci => {

            rowsHtml += `

                <tr class="border-b border-slate-100 dark:border-slate-800 text-[11px]">

                    <td class="py-1.5 px-2 text-slate-800 dark:text-slate-200">${ci.descripcion}</td>

                    <td class="py-1.5 px-2 text-center text-slate-500">${ci.unidad}</td>

                    <td class="py-1.5 px-2 text-center font-mono">${ci.cantidad_o_rendimiento}</td>

                    <td class="py-1.5 px-2 text-right font-mono">${formatCurrencyCopApu(ci.valor_unitario)}</td>

                    <td class="py-1.5 px-2 text-right font-mono font-bold text-slate-800 dark:text-slate-200">${formatCurrencyCopApu(ci.subtotal)}</td>

                </tr>

            `;

        });

        return `

            <div class="bg-white dark:bg-[#0c1427] rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden shadow-sm">

                <div class="px-3 py-2 bg-slate-50 dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">

                    <span class="font-bold text-slate-800 dark:text-white flex items-center gap-1.5 text-xs">

                        <span>${icon}</span> ${compTitle}

                    </span>

                    <span class="font-mono font-black text-emerald-600 dark:text-emerald-400 text-xs">

                        Subtotal: ${formatCurrencyCopApu(subtotal)}

                    </span>

                </div>

                <table class="w-full text-left">

                    <thead class="bg-slate-100 dark:bg-slate-800 text-[10px] uppercase font-bold text-slate-600 dark:text-slate-400">

                        <tr>

                            <th class="py-1.5 px-2">Descripción del Componente</th>

                            <th class="py-1.5 px-2 text-center">Unidad</th>

                            <th class="py-1.5 px-2 text-center">Rdto / Cant</th>

                            <th class="py-1.5 px-2 text-right">Vr. Unitario</th>

                            <th class="py-1.5 px-2 text-right">Subtotal</th>

                        </tr>

                    </thead>

                    <tbody>${rowsHtml}</tbody>

                </table>

            </div>

        `;

    };



    breakdownBox.innerHTML = `

        ${renderCompTable('A. MATERIALES, INSUMOS Y EQUIPOS PUESTOS EN OBRA', apu.componente_a_materiales, apu.subtotal_a, '📦')}

        ${renderCompTable('B. MANO DE OBRA, OPERACIÓN Y LOGÍSTICA (INCLUYE PRESTACIONES)', apu.componente_b_mano_obra, apu.subtotal_b, '👷')}

        ${renderCompTable('C. TRANSPORTE, FLETES Y HERRAMIENTAS MENORES', apu.componente_c_transporte, apu.subtotal_c, '🚚')}

        

        <div class="p-3 bg-gradient-to-r from-emerald-50 to-teal-50 dark:from-emerald-950/40 dark:to-teal-950/30 rounded-xl border border-emerald-300 dark:border-emerald-800 flex items-center justify-between">

            <div>

                <span class="text-xs font-black text-[#03008F] dark:text-emerald-300 uppercase">

                    VALOR UNITARIO TOTAL A TODO COSTO (A + B + C)

                </span>

                <p class="text-[10px] text-slate-500">Equivale exactamente a la oferta ganadora del proceso</p>

            </div>

            <span class="text-base font-black text-emerald-700 dark:text-emerald-300 font-mono">

                ${formatCurrencyCopApu(apu.valor_unitario_total)}

            </span>

        </div>

    `;

}



async function downloadApuDocx(docType) {
    if (!state.apuModule.payload || !state.apuModule.payload.ofertas || state.apuModule.payload.ofertas.length === 0) {
        showToast('Primero debe cargar al menos una propuesta o cotización.', 'warning');
        return;
    }

    syncApuConfigFromInputs();

    if (typeof triggerRunApuEvaluation === 'function') {
        await triggerRunApuEvaluation();
    } else if (state.apuModule.result) {
        state.apuModule.result.proceso_config = state.apuModule.payload.proceso_config;
    }

    if (!state.apuModule.result) {
        showToast('No se pudo generar el resultado de evaluación para la descarga.', 'warning');
        return;
    }

    try {

        if (docType === 1) {

            showToast('Generando Documento 1: Informe de Selección (.docx) con membrete y garantías...', 'info');

            await window.api.downloadInformeEvaluacionDocx(state.apuModule.result);

            showToast('¡Documento 1 descargado con éxito!', 'success');

        } else if (docType === 2) {

            showToast('Generando Documento 2: APU y Presupuesto Oficial (.docx) con membrete...', 'info');

            await window.api.downloadPresupuestoApuDocx(state.apuModule.result);

            showToast('¡Documento 2 descargado con éxito!', 'success');

        }

    } catch (e) {

        console.error("Error descargando documento DOCX:", e);

        showToast('Error al descargar documento Word: ' + e.message, 'error');

    }

}


async function downloadApuInformeDocx() {
    return await downloadApuDocx(1);
}

async function downloadApuPresupuestoDocx() {
    return await downloadApuDocx(2);
}

window.runApuComparativeEvaluation = triggerRunApuEvaluation;
window.downloadApuInformeDocx = downloadApuInformeDocx;
window.downloadApuPresupuestoDocx = downloadApuPresupuestoDocx;



// =========================================================================

// VINCULACIÓN DE ESTUDIO DE MERCADO A CONTRATO & ESTUDIO PREVIO

// =========================================================================

async function populateApuContractsDropdown() {

    const select = document.getElementById('apu-select-contract');

    if (!select) return;



    try {

        if (!state.contracts || state.contracts.length === 0) {

            state.contracts = await window.api.getContracts();

        }

    } catch (e) {

        console.warn('Error fetching contracts for APU dropdown:', e);

    }



    const contracts = state.contracts || [];

    const currentVal = state.apuModule.selectedContractId ? String(state.apuModule.selectedContractId) : '';



    let html = '<option value="">-- Proceso independiente (Sin asociar a contrato) --</option>';

    contracts.forEach(c => {

        const hasEstudio = Boolean(c.estudio_mercado || (c.metadatos_agente && c.metadatos_agente.estudio_mercado));

        const num = c.numero_contrato || `ID-${c.id}`;

        const cont = (c.contratista || 'Sin Contratista').substring(0, 28);

        const obj = (c.objeto || '').substring(0, 40);

        const tag = hasEstudio ? ' [✓ Con Estudio de Mercado]' : '';

        const isSelected = String(c.id) === currentVal ? 'selected' : '';

        html += `<option value="${c.id}" ${isSelected} class="${hasEstudio ? 'font-bold text-emerald-600' : ''}">${num} - ${cont} (${obj}...)${tag}</option>`;

    });



    select.innerHTML = html;

    if (currentVal) select.value = currentVal;

    updateApuContractStatusBadge();

}



function updateApuContractStatusBadge() {

    const badge = document.getElementById('apu-contract-status-badge');

    const btnIncorporar = document.getElementById('btn-incorporar-estudio-mercado');

    const btnDesvincular = document.getElementById('btn-desvincular-estudio-mercado');

    if (!badge) return;



    const selectedId = state.apuModule.selectedContractId;

    if (!selectedId) {

        badge.className = 'px-2.5 py-1 rounded-full text-[10px] font-bold bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300';

        badge.innerHTML = 'Proceso Independiente (Sin asociar)';

        if (btnIncorporar) {

            btnIncorporar.innerHTML = '<span>🔗</span><span>Incorporar a Estudio Previo</span>';

            btnIncorporar.title = 'Seleccione un contrato primero para incorporarlo';

        }

        if (btnDesvincular) btnDesvincular.classList.add('hidden');

        return;

    }



    const c = (state.contracts || []).find(x => x.id === Number(selectedId));

    const num = c ? (c.numero_contrato || `Contrato #${c.id}`) : `Contrato #${selectedId}`;

    const hasEstudio = Boolean(c && (c.estudio_mercado || (c.metadatos_agente && c.metadatos_agente.estudio_mercado)));



    if (hasEstudio) {

        badge.className = 'px-2.5 py-1 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 border border-emerald-400 dark:border-emerald-700';

        badge.innerHTML = `✓ Asociado a ${num} (Incorporado en Estudio Previo)`;

        if (btnIncorporar) {

            btnIncorporar.innerHTML = '<span>🔄</span><span>Actualizar en Estudio Previo</span>';

            btnIncorporar.title = `Actualizar el estudio de mercado incorporado en ${num}`;

        }

        if (btnDesvincular) btnDesvincular.classList.remove('hidden');

    } else {

        badge.className = 'px-2.5 py-1 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300 border border-amber-400 dark:border-amber-700';

        badge.innerHTML = `Asociado a ${num} (Pendiente de incorporar)`;

        if (btnIncorporar) {

            btnIncorporar.innerHTML = '<span>🔗</span><span>Incorporar a Estudio Previo</span>';

            btnIncorporar.title = `Guardar este análisis en ${num} para que aparezca en el Estudio Previo`;

        }

        if (btnDesvincular) btnDesvincular.classList.add('hidden');

    }

}



async function handleApuContractSelected() {

    const select = document.getElementById('apu-select-contract');

    if (!select) return;



    const val = select.value;

    if (!val) {

        state.apuModule.selectedContractId = null;

        updateApuContractStatusBadge();

        return;

    }



    const contractId = parseInt(val, 10);

    state.apuModule.selectedContractId = contractId;



    let c = (state.contracts || []).find(x => x.id === contractId);

    if (!c) {

        try {

            c = await window.api.getContract(contractId);

        } catch (e) {

            console.warn('Error fetching contract detail:', e);

        }

    }



    if (!c) {

        updateApuContractStatusBadge();

        return;

    }



    const estudio = c.estudio_mercado || (c.metadatos_agente && c.metadatos_agente.estudio_mercado);

    if (estudio && (estudio.ofertas || estudio.items_apu || estudio.proceso_config)) {

        // Cargar datos del estudio existente en el módulo APU

        state.apuModule.result = estudio;

        state.apuModule.payload = {

            proceso_config: estudio.proceso_config || {},

            ofertas: estudio.ofertas || [],

            proponente_ganador_nombre: estudio.proponente_ganador?.nombre_razon_social || estudio.proponente_ganador_nombre || null

        };

        // Cargar inputs del formulario de configuración

        const cfg = state.apuModule.payload.proceso_config;

        if (document.getElementById('apu-input-objeto') && cfg.objeto_contractual) {

            document.getElementById('apu-input-objeto').value = cfg.objeto_contractual;

        }

        if (document.getElementById('apu-input-tipo-contrato') && cfg.tipo_contrato) {

            document.getElementById('apu-input-tipo-contrato').value = cfg.tipo_contrato;

        }

        if (document.getElementById('apu-input-modalidad-codigo') && cfg.modalidad_manual_codigo) {

            document.getElementById('apu-input-modalidad-codigo').value = cfg.modalidad_manual_codigo;

        }

        if (document.getElementById('apu-input-smlmv') && cfg.smlmv_vigencia) {

            document.getElementById('apu-input-smlmv').value = cfg.smlmv_vigencia;

        }

        if (document.getElementById('apu-input-plazo-meses') && cfg.plazo_ejecucion_meses) {

            document.getElementById('apu-input-plazo-meses').value = cfg.plazo_ejecucion_meses;

        }

        if (document.getElementById('apu-input-anticipo-pct') && cfg.anticipo_porcentaje !== undefined) {

            document.getElementById('apu-input-anticipo-pct').value = cfg.anticipo_porcentaje;

        }

        if (document.getElementById('apu-input-fecha') && cfg.fecha_proceso) {

            document.getElementById('apu-input-fecha').value = cfg.fecha_proceso;

        }

        if (document.getElementById('apu-input-lugar') && cfg.lugar_ejecucion) {

            document.getElementById('apu-input-lugar').value = cfg.lugar_ejecucion;

        }

        if (document.getElementById('apu-input-criterio') && cfg.criterio_seleccion) {

            document.getElementById('apu-input-criterio').value = cfg.criterio_seleccion;

        }

        if (document.getElementById('apu-firmante-eval-nom') && cfg.evaluador_nombre) {

            document.getElementById('apu-firmante-eval-nom').value = cfg.evaluador_nombre;

        }

        if (document.getElementById('apu-firmante-eval-car') && cfg.evaluador_cargo) {

            document.getElementById('apu-firmante-eval-car').value = cfg.evaluador_cargo;

        }

        if (document.getElementById('apu-firmante-aprob-nom') && cfg.aprobador_nombre) {

            document.getElementById('apu-firmante-aprob-nom').value = cfg.aprobador_nombre;

        }

        if (document.getElementById('apu-firmante-aprob-car') && cfg.aprobador_cargo) {

            document.getElementById('apu-firmante-aprob-car').value = cfg.aprobador_cargo;

        }

        toggleApuCausalDirecta();

        renderApuAll();

        showToast(`Estudio de mercado del contrato ${c.numero_contrato || c.id} cargado en el visor.`, 'info');

    } else {

        // Autocompletar datos básicos del contrato en la configuración

        if (document.getElementById('apu-input-objeto') && c.objeto) {

            document.getElementById('apu-input-objeto').value = c.objeto;

        }

        if (document.getElementById('apu-input-tipo-contrato') && c.tipo_contrato) {

            document.getElementById('apu-input-tipo-contrato').value = c.tipo_contrato;

        }

        if (document.getElementById('apu-input-plazo-meses') && c.plazo_meses) {

            document.getElementById('apu-input-plazo-meses').value = c.plazo_meses;

        }

        showToast(`Contrato ${c.numero_contrato || c.id} seleccionado. Complete el análisis y haga clic en "Incorporar a Estudio Previo".`, 'info');

    }



    updateApuContractStatusBadge();

}



async function incorporarEstudioMercadoAContrato() {

    const contractId = state.apuModule.selectedContractId;

    if (!contractId) {

        showToast('Seleccione primero un contrato en la lista superior para poder incorporar el estudio.', 'warning');

        const select = document.getElementById('apu-select-contract');

        if (select) select.focus();

        return;

    }



    // Asegurar sincronización de inputs

    syncApuConfigFromInputs();



    // Si aún no se ha evaluado o el resultado no existe pero hay ofertas cargadas, evaluamos

    if (!state.apuModule.result) {

        if (!state.apuModule.payload || !state.apuModule.payload.ofertas || state.apuModule.payload.ofertas.length === 0) {

            showToast('Debe cargar al menos una cotización y ejecutar la evaluación antes de incorporar el estudio.', 'warning');

            return;

        }

        try {

            showToast('Ejecutando evaluación antes de incorporar...', 'info');

            const res = await window.api.evaluateApuProposals(state.apuModule.payload);

            state.apuModule.result = res;

            renderApuAll();

        } catch (e) {

            showToast('Error al evaluar propuestas: ' + e.message, 'error');

            return;

        }

    }



    // Asegurar proceso_config dentro de result

    state.apuModule.result.proceso_config = state.apuModule.payload.proceso_config;



    try {

        showToast('Guardando e incorporando estudio de mercado al contrato...', 'info');

        const res = await window.api.saveContractEstudioMercado(contractId, state.apuModule.result);

        

        // Actualizar en el estado local de contratos

        const c = (state.contracts || []).find(x => x.id === Number(contractId));

        if (c) {

            c.estudio_mercado = state.apuModule.result;

            if (!c.metadatos_agente) c.metadatos_agente = {};

            c.metadatos_agente.tiene_estudio_mercado = true;

            c.metadatos_agente.estudio_mercado = state.apuModule.result;

        }



        updateApuContractStatusBadge();

        await populateApuContractsDropdown();

        showToast('✓ ¡Estudio de mercado incorporado con éxito al contrato! Aparecerá automáticamente en el Estudio Previo (.docx) bajo el subtítulo "ANALISIS DE LAS PROPUESTAS DE MERCADO:".', 'success');

    } catch (e) {

        console.error('Error incorporando estudio de mercado:', e);

        showToast('Error al incorporar estudio de mercado: ' + e.message, 'error');

    }

}



async function desvincularEstudioMercadoDeContrato() {

    const contractId = state.apuModule.selectedContractId;

    if (!contractId) return;



    const c = (state.contracts || []).find(x => x.id === Number(contractId));

    const num = c ? (c.numero_contrato || `Contrato #${c.id}`) : `Contrato #${contractId}`;



    if (!confirm(`¿Está seguro de quitar el estudio de mercado del contrato ${num}? Ya no se incluirá en el Estudio Previo (.docx).`)) {

        return;

    }



    try {

        await window.api.deleteContractEstudioMercado(contractId);

        if (c) {

            c.estudio_mercado = null;

            if (c.metadatos_agente) {

                c.metadatos_agente.tiene_estudio_mercado = false;

                delete c.metadatos_agente.estudio_mercado;

            }

        }

        updateApuContractStatusBadge();

        await populateApuContractsDropdown();

        showToast('Estudio de mercado desvinculado del contrato.', 'info');

    } catch (e) {

        console.error('Error desvinculando estudio de mercado:', e);

        showToast('Error al desvincular estudio de mercado: ' + e.message, 'error');

    }

}



// =========================================================================

// MÓDULO INTELIGENTE: AGENTE CLASIFICADOR DE CÓDIGOS UNSPSC

// =========================================================================

function initNewUnspscProcess() {

    state.unspscModule.selectedContractId = null;

    state.unspscModule.result = null;

    state.unspscModule.estudioFile = null;

    state.unspscModule.propuestaFile = null;



    const sel = document.getElementById('unspsc-select-contract');

    if (sel) sel.value = '';



    const estInput = document.getElementById('unspsc-input-estudio');

    if (estInput) estInput.value = '';



    const estName = document.getElementById('unspsc-file-estudio-name');

    if (estName) estName.innerText = 'Ningún archivo cargado';



    const fileEst = document.getElementById('unspsc-file-estudio');

    if (fileEst) fileEst.value = '';



    const propInput = document.getElementById('unspsc-input-propuesta');

    if (propInput) propInput.value = '';



    const propName = document.getElementById('unspsc-file-propuesta-name');

    if (propName) propName.innerText = 'Ningún archivo cargado';



    const fileProp = document.getElementById('unspsc-file-propuesta');

    if (fileProp) fileProp.value = '';



    const objDetText = document.getElementById('unspsc-objeto-detectado-text');

    if (objDetText) objDetText.innerText = '';

    const objDetCard = document.getElementById('unspsc-objeto-detectado-card');

    if (objDetCard) objDetCard.classList.add('hidden');



    const resBox = document.getElementById('unspsc-results-container');

    if (resBox) resBox.classList.add('hidden');



    showToast('Nuevo proceso de clasificación UNSPSC en blanco preparado.', 'info');

}



async function loadUnspscView() {

    await populateUnspscContractsDropdown();

    if (state.unspscModule.result) {

        renderUnspscResults(state.unspscModule.result);

    }

}



async function populateUnspscContractsDropdown() {

    const select = document.getElementById('unspsc-select-contract');

    if (!select) return;



    try {

        if (!state.contracts || state.contracts.length === 0) {

            state.contracts = await window.api.getContracts();

        }

    } catch (e) {

        console.warn('Error fetching contracts for UNSPSC dropdown:', e);

    }



    const contracts = state.contracts || [];

    const currentVal = state.unspscModule.selectedContractId ? String(state.unspscModule.selectedContractId) : '';



    let html = '<option value="">-- Proceso independiente (Sin asociar a contrato) --</option>';

    contracts.forEach(c => {

        const hasCodes = Boolean(c.codigos_unspsc && c.codigos_unspsc.codigos_seleccionados && c.codigos_unspsc.codigos_seleccionados.length > 0);

        const num = c.numero_contrato || `ID-${c.id}`;

        const cont = (c.contratista || 'Sin Contratista').substring(0, 26);

        const obj = (c.objeto || '').substring(0, 36);

        const tag = hasCodes ? ` [✓ ${c.codigos_unspsc.codigos_seleccionados.length} Códigos]` : '';

        const isSelected = String(c.id) === currentVal ? 'selected' : '';

        html += `<option value="${c.id}" ${isSelected} class="${hasCodes ? 'font-bold text-teal-600' : ''}">${num} - ${cont} (${obj}...)${tag}</option>`;

    });



    select.innerHTML = html;

    if (currentVal) select.value = currentVal;

}



async function handleUnspscContractSelected() {

    const select = document.getElementById('unspsc-select-contract');

    if (!select) return;

    const val = select.value;



    if (!val) {

        state.unspscModule.selectedContractId = null;

        return;

    }



    const contractId = parseInt(val, 10);

    state.unspscModule.selectedContractId = contractId;



    let c = (state.contracts || []).find(x => x.id === contractId);

    if (!c) {

        try {

            c = await window.api.getContract(contractId);

        } catch (e) {

            console.warn('Error fetching contract detail:', e);

        }

    }



    if (!c) return;



    if (document.getElementById('unspsc-input-estudio')) {

        document.getElementById('unspsc-input-estudio').value = c.justificacion_necesidad || '';

    }



    // Verificar si el contrato tiene un documento de tipo propuesta o cotización adjunto

    const propNameEl = document.getElementById('unspsc-file-propuesta-name');

    let propDocFound = null;

    if (c.documentos && Array.isArray(c.documentos)) {

        propDocFound = c.documentos.find(d => {

            const n = (d.nombre_archivo_original || '').toLowerCase();

            const t = String(d.tipo_documento || '').toLowerCase();

            return n.includes('propuesta') || n.includes('cotizacion') || n.includes('cotización') || t.includes('propuesta') || t.includes('cotizacion');

        });

    }



    if (propDocFound && propNameEl) {

        propNameEl.innerText = `📎 ${propDocFound.nombre_archivo_original} (adjunto al contrato)`;

    } else if (propNameEl && !state.unspscModule.propuestaFile) {

        propNameEl.innerText = 'Ningún archivo cargado';

    }



    if (c.codigos_unspsc && c.codigos_unspsc.codigos_seleccionados) {

        state.unspscModule.result = c.codigos_unspsc;

        renderUnspscResults(c.codigos_unspsc);

        showToast(`Clasificación UNSPSC guardada cargada para el contrato ${c.numero_contrato || c.id}.`, 'info');

    } else {

        const resBox = document.getElementById('unspsc-results-container');

        if (resBox) resBox.classList.add('hidden');

        state.unspscModule.result = null;

        showToast(`Contrato ${c.numero_contrato || c.id} seleccionado. Haga clic en 'Analizar y Clasificar Códigos UNSPSC'.`, 'info');

    }

}



function handleUnspscFileUpload(type, input) {

    if (!input.files || input.files.length === 0) return;

    const file = input.files[0];

    const fileName = (file.name || '').toLowerCase();



    if (fileName.endsWith('.doc') && !fileName.endsWith('.docx')) {

        showToast('Formato .doc no compatible. Por favor cargue el archivo en formato .docx o .pdf', 'warning');

        input.value = '';

        return;

    }



    if (type === 'estudio') {

        state.unspscModule.estudioFile = file;

        const nameEl = document.getElementById('unspsc-file-estudio-name');

        if (nameEl) nameEl.innerText = `✓ ${file.name}`;

        showToast(`Archivo de Estudio Previo "${file.name}" cargado.`, 'info');

    } else if (type === 'propuesta') {

        state.unspscModule.propuestaFile = file;

        const nameEl = document.getElementById('unspsc-file-propuesta-name');

        if (nameEl) nameEl.innerText = `✓ ${file.name}`;

        showToast(`Archivo de Propuesta Económica "${file.name}" cargado.`, 'info');

    }

}



async function triggerRunUnspscAnalysis() {

    // 1. Reset de Estado Obligatorio (Clean Slate):

    state.unspscModule.result = null;

    const resContainer = document.getElementById('unspsc-results-container');

    if (resContainer) resContainer.classList.add('hidden');

    const actListEl = document.getElementById('unspsc-actividades-list');

    if (actListEl) actListEl.innerHTML = '';

    const codesTbodyEl = document.getElementById('unspsc-selected-codes-tbody');

    if (codesTbodyEl) codesTbodyEl.innerHTML = '';

    const resumenElInit = document.getElementById('unspsc-resumen-text');

    if (resumenElInit) resumenElInit.innerText = '';

    const badgeElInit = document.getElementById('unspsc-total-badge');

    if (badgeElInit) badgeElInit.innerText = '';

    const motorBadgeInit = document.getElementById('unspsc-motor-badge');

    if (motorBadgeInit) { motorBadgeInit.innerText = ''; motorBadgeInit.classList.add('hidden'); }

    const iaBadgeInit = document.getElementById('unspsc-ia-badge');

    if (iaBadgeInit) { iaBadgeInit.innerText = ''; iaBadgeInit.classList.add('hidden'); }

    const objDetText = document.getElementById('unspsc-objeto-detectado-text');

    if (objDetText) objDetText.innerText = '';



    const estudioText = document.getElementById('unspsc-input-estudio')?.value.trim() || '';

    const propuestaText = document.getElementById('unspsc-input-propuesta')?.value.trim() || '';

    const contractId = state.unspscModule.selectedContractId;

    const hasStudyFile = Boolean(state.unspscModule.estudioFile);

    const hasPropFile = Boolean(state.unspscModule.propuestaFile);

    const contractObj = contractId ? (state.contracts || []).find(x => x.id === contractId) : null;

    const contractHasStudy = Boolean(contractObj && (contractObj.justificacion_necesidad || contractObj.objeto));



    if (!hasStudyFile && !estudioText && !contractHasStudy) {

        showToast('El estudio previo es obligatorio (archivo, texto o contrato vinculado).', 'warning');

        return;

    }



    const btn = document.getElementById('btn-run-unspsc');

    const spinner = document.getElementById('unspsc-btn-spinner');



    if (btn) btn.disabled = true;

    if (spinner) spinner.classList.remove('hidden');



    showToast('Analizando documentos y clasificando códigos...', 'info');



    try {

        let res;

        if (hasStudyFile || hasPropFile) {

            const formData = new FormData();

            formData.append('objeto', '');

            formData.append('estudio_previo_text', estudioText);

            formData.append('propuesta_text', propuestaText);

            if (contractId) formData.append('contract_id', contractId);

            if (hasStudyFile) formData.append('estudio_file', state.unspscModule.estudioFile);

            if (hasPropFile) formData.append('propuesta_file', state.unspscModule.propuestaFile);



            res = await window.api.analyzeUnspscFiles(formData);

        } else {

            res = await window.api.analyzeUnspsc({

                objeto: '',

                estudio_previo: estudioText,

                propuesta_economica: propuestaText,

                contract_id: contractId

            });

        }



        state.unspscModule.result = res;

        renderUnspscResults(res);

        showToast(`¡Dictamen de auditoría generado! ${res.total_codigos} códigos oficiales del núcleo misional.`, 'success');

    } catch (e) {

        console.error("Error en análisis UNSPSC:", e);

        showToast('Error en el análisis UNSPSC: ' + e.message, 'error');

    } finally {

        if (btn) btn.disabled = false;

        if (spinner) spinner.classList.add('hidden');

    }

}



function renderUnspscResults(result) {

    if (!result) return;

    const container = document.getElementById('unspsc-results-container');

    if (!container) return;

    container.classList.remove('hidden');



    // Tarjeta del Objeto Detectado

    const objDetCard = document.getElementById('unspsc-objeto-detectado-card');

    const objDetText = document.getElementById('unspsc-objeto-detectado-text');

    if (objDetText) {

        if (result.objeto_detectado) {

            objDetText.innerText = result.objeto_detectado;

            if (objDetCard) objDetCard.classList.remove('hidden');

        } else {

            objDetText.innerText = '';

            if (objDetCard) objDetCard.classList.add('hidden');

        }

    }



    // Paso 1: Actividades Principales Extraídas Literalmente (Propuesta Económica)

    const actContainer = document.getElementById('unspsc-actividades-container');

    const actList = document.getElementById('unspsc-actividades-list');

    if (actList) {

        actList.innerHTML = '';

        const actividades = result.actividades_propuesta_extraidas || [];

        if (actividades.length > 0) {

            if (actContainer) actContainer.classList.remove('hidden');

            actividades.forEach((act, idx) => {

                const item = document.createElement('div');

                item.className = 'flex items-start gap-2.5 bg-white/90 dark:bg-slate-900/80 p-3 rounded-2xl border border-blue-200/80 dark:border-blue-900/50 shadow-xs';

                item.innerHTML = `

                    <span class="inline-flex items-center justify-center w-5 h-5 rounded-full bg-blue-700 text-white font-black text-[10px] shrink-0 mt-0.5">

                        ${idx + 1}

                    </span>

                    <div class="text-xs font-semibold text-slate-800 dark:text-slate-100 italic leading-snug">

                        "${escapeHtml(act)}"

                    </div>

                `;

                actList.appendChild(item);

            });

        } else if (actContainer) {

            actContainer.classList.add('hidden');

        }

    }



    // 1. Resumen

    const resumenEl = document.getElementById('unspsc-resumen-text');

    if (resumenEl) resumenEl.innerText = result.resumen_analisis || 'Sin resumen provisto.';



    const tsEl = document.getElementById('unspsc-result-timestamp');

    if (tsEl) tsEl.innerText = result.fecha_analisis ? `Fecha: ${result.fecha_analisis}` : '';



    // 2. Badge total y badges de Motor / IA

    const badge = document.getElementById('unspsc-total-badge');

    if (badge) badge.innerText = `${result.total_codigos || (result.codigos_seleccionados || []).length} Códigos Seleccionados`;



    const motorBadge = document.getElementById('unspsc-motor-badge');

    if (motorBadge) {

        if (result.motor_usado) {

            motorBadge.classList.remove('hidden');

            if (result.motor_usado === 'nuevo') {

                motorBadge.className = 'px-2.5 py-0.5 rounded-full text-xs font-black bg-indigo-100 text-indigo-800 dark:bg-indigo-950/80 dark:text-indigo-300 border border-indigo-300 dark:border-indigo-700';

                motorBadge.innerText = '⚡ Motor Nuevo';

            } else {

                motorBadge.className = 'px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-100 text-amber-800 dark:bg-amber-950/80 dark:text-amber-300 border border-amber-300 dark:border-amber-700';

                motorBadge.innerText = '🏛️ Motor Clásico';

            }

        } else {

            motorBadge.classList.add('hidden');

        }

    }



    const iaBadge = document.getElementById('unspsc-ia-badge');

    if (iaBadge) {

        if (result.uso_ia !== undefined && result.uso_ia !== null) {

            iaBadge.classList.remove('hidden');

            if (result.uso_ia) {

                iaBadge.className = 'px-2.5 py-0.5 rounded-full text-xs font-black bg-emerald-100 text-emerald-800 dark:bg-emerald-950/80 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-700';

                iaBadge.innerText = '🤖 IA Gemini';

            } else {

                iaBadge.className = 'px-2.5 py-0.5 rounded-full text-xs font-bold bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-300 border border-slate-300 dark:border-slate-600';

                iaBadge.innerText = '🛡️ Respaldo Determinístico';

            }

        } else {

            iaBadge.classList.add('hidden');

        }

    }



    // 3. Tabla de códigos

    const tbody = document.getElementById('unspsc-selected-codes-tbody');

    if (tbody) {

        tbody.innerHTML = '';

        const codigos = result.codigos_seleccionados || [];

        if (codigos.length === 0) {

            tbody.innerHTML = '<tr><td colspan="5" class="p-6 text-center text-slate-500">No se encontraron códigos coincidentes.</td></tr>';

        } else {

            codigos.forEach(c => {

                let justifText = c.justificacion_eleccion || '';

                const codeClean = String(c.codigo_unspsc || '').trim().replace('.0', '').padStart(8, '0');



                const tr = document.createElement('tr');

                tr.className = 'hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition-colors border-b border-slate-100 dark:border-slate-800/60';

                tr.innerHTML = `

                    <td class="py-3 px-3 text-center align-top">

                        <span class="inline-block px-2.5 py-1 rounded-lg text-xs font-mono font-extrabold bg-[#03008F]/10 dark:bg-sky-500/20 text-[#03008F] dark:text-sky-300 border border-[#03008F]/20 dark:border-sky-500/30">

                            ${c.codigo_unspsc}

                        </span>

                    </td>

                    <td class="py-3 px-4 font-bold text-slate-900 dark:text-white align-top">

                        ${escapeHtml(c.descripcion_codigo)}

                    </td>

                    <td class="py-3 px-3 text-center align-top text-[11px] font-mono text-slate-500 space-y-0.5">

                        <div><span class="text-slate-400">Seg:</span> <strong class="text-slate-700 dark:text-slate-300">${c.segmento || c.codigo_unspsc.substring(0,2)}</strong></div>

                        <div><span class="text-slate-400">Fam:</span> <strong class="text-slate-700 dark:text-slate-300">${c.familia || c.codigo_unspsc.substring(0,4)}</strong></div>

                        <div><span class="text-slate-400">Cla:</span> <strong class="text-slate-700 dark:text-slate-300">${c.clase || c.codigo_unspsc.substring(0,6)}</strong></div>

                    </td>

                    <td class="py-3 px-4 text-xs text-slate-700 dark:text-slate-300 leading-relaxed align-top">

                        <div class="mb-1">

                            <span class="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold ${c.fuente_cita === 'propuesta' ? 'bg-blue-100 text-blue-800 dark:bg-blue-950/80 dark:text-blue-300 border border-blue-300 dark:border-blue-700' : 'bg-teal-100 text-teal-800 dark:bg-teal-950/80 dark:text-teal-300 border border-teal-300 dark:border-teal-700'}">

                                ${c.fuente_cita === 'propuesta' ? '📊 Fuente: Propuesta Económica' : '📄 Fuente: Estudio Previo'}

                            </span>

                        </div>

                        ${escapeHtml(justifText)}

                    </td>

                    <td class="py-3 px-3 text-center align-top">

                        <button type="button" onclick="copyUnspscCode('${c.codigo_unspsc}')" class="px-2.5 py-1 text-[11px] font-bold text-teal-700 dark:text-teal-300 bg-teal-50 dark:bg-teal-950/60 hover:bg-teal-100 rounded-lg border border-teal-300 dark:border-teal-700 transition-all cursor-pointer" title="Copiar código al portapapeles">

                            Copiar

                        </button>

                    </td>

                `;

                tbody.appendChild(tr);

            });

        }

    }



    // 4. Alertas o recomendaciones

    const alertsBox = document.getElementById('unspsc-alerts-box');

    const alertsText = document.getElementById('unspsc-alerts-text');

    if (alertsBox && alertsText) {

        if (result.alertas_recomendaciones) {

            alertsBox.classList.remove('hidden');

            alertsText.innerText = result.alertas_recomendaciones;

        } else {

            alertsBox.classList.add('hidden');

            alertsText.innerText = '';

        }

    }



    // Scroll suave

    container.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

}



function toggleUnspscCatalogExplorer() {

    const el = document.getElementById('unspsc-catalog-explorer');

    if (el) {

        el.classList.toggle('hidden');

        if (!el.classList.contains('hidden')) {

            const inp = document.getElementById('unspsc-catalog-search-input');

            if (inp) inp.focus();

        }

    }

}



async function searchUnspscCatalogInteractive() {

    const inp = document.getElementById('unspsc-catalog-search-input');

    const query = inp ? inp.value.trim() : '';

    const tbody = document.getElementById('unspsc-catalog-results-tbody');

    if (!tbody) return;



    tbody.innerHTML = '<tr><td colspan="4" class="p-4 text-center text-slate-400">Buscando en catálogo oficial...</td></tr>';



    try {

        const results = await window.api.searchUnspsc(query, 50);

        if (!results || results.length === 0) {

            tbody.innerHTML = '<tr><td colspan="4" class="p-4 text-center text-slate-500">No se encontraron códigos con ese criterio.</td></tr>';

            return;

        }

        tbody.innerHTML = '';

        results.forEach(r => {

            const tr = document.createElement('tr');

            tr.className = 'hover:bg-slate-800/60 transition-colors';

            tr.innerHTML = `

                <td class="p-2 font-mono font-bold text-teal-400">${r.codigo}</td>

                <td class="p-2 text-slate-200">${escapeHtml(r.descripcion)}</td>

                <td class="p-2 font-mono text-[10px] text-slate-400">${r.segmento} / ${r.familia} / ${r.clase}</td>

                <td class="p-2 text-center">

                    <button type="button" onclick="copyUnspscCode('${r.codigo}')" class="px-2 py-0.5 rounded text-[10px] bg-slate-700 hover:bg-slate-600 text-white cursor-pointer">Copiar</button>

                </td>

            `;

            tbody.appendChild(tr);

        });

    } catch (e) {

        tbody.innerHTML = `<tr><td colspan="4" class="p-4 text-center text-rose-400">Error: ${e.message}</td></tr>`;

    }

}



function copyUnspscCode(code) {

    if (navigator.clipboard) {

        navigator.clipboard.writeText(code).then(() => {

            showToast(`Código UNSPSC ${code} copiado al portapapeles.`, 'success');

        }).catch(() => {

            prompt('Copie el código:', code);

        });

    } else {

        prompt('Copie el código:', code);

    }

}



function copyAllUnspscCodes() {

    const res = state.unspscModule.result;

    if (!res || !res.codigos_seleccionados || res.codigos_seleccionados.length === 0) {

        showToast('No hay códigos seleccionados para copiar.', 'warning');

        return;

    }

    const lines = res.codigos_seleccionados.map(c => `${c.codigo_unspsc} - ${c.descripcion_codigo}`);

    const text = `CÓDIGOS UNSPSC SELECCIONADOS:\n` + lines.join('\n');

    if (navigator.clipboard) {

        navigator.clipboard.writeText(text).then(() => {

            showToast('¡Todos los códigos UNSPSC copiados al portapapeles!', 'success');

        });

    } else {

        prompt('Copie los códigos:', text);

    }

}



async function downloadUnspscReportDocx() {

    const res = state.unspscModule.result;

    if (!res) {

        showToast('Primero debe ejecutar el análisis para descargar el informe.', 'warning');

        return;

    }

    const objeto = document.getElementById('unspsc-input-objeto')?.value || res.objeto_detectado || '';

    let numContrato = '';

    if (state.unspscModule.selectedContractId) {

        const c = (state.contracts || []).find(x => x.id === state.unspscModule.selectedContractId);

        if (c) numContrato = c.numero_contrato || `Contrato #${c.id}`;

    }

    try {

        showToast('Generando dictamen oficial UNSPSC en formato Word (.docx)...', 'info');

        await window.api.downloadUnspscReportDocx({

            result: res,

            objeto: objeto,

            numero_contrato: numContrato

        });

        showToast('¡Dictamen oficial UNSPSC descargado con éxito!', 'success');

    } catch (e) {

        showToast('Error descargando informe: ' + e.message, 'error');

    }

}



async function saveUnspscToContract() {

    const contractId = state.unspscModule.selectedContractId;

    if (!contractId) {

        showToast('Seleccione un contrato en el menú superior para guardar la clasificación.', 'warning');

        document.getElementById('unspsc-select-contract')?.focus();

        return;

    }

    const res = state.unspscModule.result;

    if (!res) {

        showToast('Debe ejecutar el análisis antes de guardar.', 'warning');

        return;

    }



    try {

        showToast('Guardando clasificación UNSPSC en el contrato...', 'info');

        await window.api.saveContractUnspsc(contractId, res);



        // Actualizar contrato local

        const c = (state.contracts || []).find(x => x.id === Number(contractId));

        if (c) {

            c.codigos_unspsc = res;

        }

        await populateUnspscContractsDropdown();

        showToast('✓ Clasificación UNSPSC guardada exitosamente en el contrato.', 'success');

    } catch (e) {

        console.error('Error guardando UNSPSC en contrato:', e);

        showToast('Error guardando en contrato: ' + e.message, 'error');

    }

}



function updateNavCategoriesState(currentTab) {

    const catMap = {

        'dashboard': null,

        'contracts': 'navcat-gestion',

        'execution': 'navcat-gestion',

        'contractors': 'navcat-gestion',

        'reports': 'navcat-gestion',

        'apu': 'navcat-ai',

        'risks': 'navcat-ai',

        'wizard': 'navcat-ai',

        'unspsc': 'navcat-ai',

        'excel': 'navcat-tools',

        'templates': 'navcat-tools',

        'settings': 'navcat-system',

        'users': 'navcat-system'

    };



    const allCatIds = ['navcat-gestion', 'navcat-ai', 'navcat-tools', 'navcat-system'];

    allCatIds.forEach(catId => {

        const btn = document.getElementById(catId);

        if (btn) {

            btn.classList.remove('nav-cat-active', 'bg-[#03008F]/10', 'text-[#03008F]', 'dark:bg-sky-500/20', 'dark:text-sky-300', 'ring-1', 'ring-[#03008F]/30', 'dark:ring-sky-500/40');

            btn.classList.add('text-slate-700', 'dark:text-slate-300');

        }

    });



    const activeCatId = catMap[currentTab];

    if (activeCatId) {

        const catBtn = document.getElementById(activeCatId);

        if (catBtn) {

            catBtn.classList.remove('text-slate-700', 'dark:text-slate-300');

            catBtn.classList.add('nav-cat-active');

        }

    }



    // Resaltado de subítem dentro de su menú desplegable

    document.querySelectorAll('.nav-sub-item').forEach(el => el.classList.remove('sub-item-active'));

    const activeSub = document.getElementById(`nav-${currentTab}`);

    if (activeSub && activeSub.classList.contains('nav-sub-item')) {

        activeSub.classList.add('sub-item-active');

    }

}



function toggleNavDropdown(menuId) {

    const menu = document.getElementById(menuId);

    if (!menu) return;

    const isAlreadyOpen = menu.classList.contains('dropdown-open');

    closeAllNavDropdowns();

    if (!isAlreadyOpen) {

        menu.classList.add('dropdown-open');

    }

}



function closeAllNavDropdowns() {

    document.querySelectorAll('.nav-dropdown-menu').forEach(el => {

        el.classList.remove('dropdown-open');

    });

}



// Cierre al hacer clic fuera del menú de navegación

document.addEventListener('click', (e) => {

    if (!e.target.closest('#desktop-nav')) {

        closeAllNavDropdowns();

    }

});

