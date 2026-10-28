/**
 * ESPY API Client Layer
 * Handles communication with FastAPI endpoints.
 */

const API_BASE = '/api';

class ApiClient {
    constructor() {
        this.baseUrl = API_BASE;
        this.apiKey = localStorage.getItem('gemini_api_key') || '';
        
        // Cargar token persistente desde localStorage o sessionStorage
        this.token = localStorage.getItem('espy_token') || sessionStorage.getItem('espy_token') || '';
        this.currentUser = null;
        try {
            const rawUser = localStorage.getItem('espy_user') || sessionStorage.getItem('espy_user');
            if (rawUser) {
                this.currentUser = JSON.parse(rawUser);
            }
        } catch (e) {
            this.currentUser = null;
        }
    }

    setToken(token) {
        this.token = token || '';
        try {
            if (token) {
                localStorage.setItem('espy_token', token);
                sessionStorage.setItem('espy_token', token);
            } else {
                localStorage.removeItem('espy_token');
                sessionStorage.removeItem('espy_token');
            }
        } catch (e) {}
    }

    getToken() {
        return this.token;
    }

    setCurrentUser(user) {
        this.currentUser = user;
        try {
            if (user) {
                localStorage.setItem('espy_user', JSON.stringify(user));
                sessionStorage.setItem('espy_user', JSON.stringify(user));
            } else {
                localStorage.removeItem('espy_user');
                sessionStorage.removeItem('espy_user');
            }
        } catch (e) {}
    }

    getCurrentUser() {
        return this.currentUser;
    }

    isLoggedIn() {
        return !!this.token;
    }

    isAdmin() {
        return !!(this.currentUser && (this.currentUser.rol === 'ADMIN' || this.currentUser.rol === 'RolUsuario.ADMIN'));
    }

    setApiKey(key) {
        this.apiKey = key;
        if (key) {
            localStorage.setItem('gemini_api_key', key);
        } else {
            localStorage.removeItem('gemini_api_key');
        }
    }

    getApiKey() {
        return this.apiKey;
    }

    async request(endpoint, options = {}) {
        const url = `${API_BASE}${endpoint}`;
        const headers = { ...options.headers };

        if (this.token) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }

        if (!options.isFormData && !headers['Content-Type']) {
            headers['Content-Type'] = 'application/json';
        }

        try {
            const response = await fetch(url, { ...options, headers });
            
            if (!response.ok) {
                if (response.status === 401) {
                    this.logout();
                    if (typeof document !== 'undefined') {
                        document.body.classList.remove('role-admin', 'role-invitado', 'role-editor');
                        if (typeof showLoginScreen === 'function') {
                            showLoginScreen();
                        }
                        if (typeof showToast === 'function') {
                            showToast("Su sesión expiró. Inicie sesión de nuevo.", "warning");
                        }
                    }
                    throw new Error("Su sesión expiró. Inicie sesión de nuevo.");
                }

                let errorMsg = `Error ${response.status}: ${response.statusText}`;
                try {
                    const errData = await response.json();
                    if (errData.detail) {
                        errorMsg = typeof errData.detail === 'string' 
                            ? errData.detail 
                            : JSON.stringify(errData.detail);
                    }
                } catch (e) {
                    // Fallback to text
                }
                throw new Error(errorMsg);
            }

            // Return blob if specified
            if (options.asBlob) {
                return await response.blob();
            }

            // If 204 No Content
            if (response.status === 204) {
                return null;
            }

            return await response.json();
        } catch (error) {
            console.error(`API Error [${endpoint}]:`, error);
            throw error;
        }
    }

    // Health
    async getHealth() {
        return this.request('/health');
    }

    // =========================================================
    // AUTHENTICATION & USER ACCESS CONTROL
    // =========================================================
    async login(documento, password) {
        const res = await this.request('/auth/login', {
            method: 'POST',
            body: JSON.stringify({ documento, password })
        });
        if (res && res.token) {
            this.setToken(res.token);
            this.setCurrentUser(res.usuario);
        }
        return res;
    }

    logout() {
        this.setToken('');
        this.setCurrentUser(null);
    }

    async getMe() {
        try {
            const user = await this.request('/auth/me');
            if (user) {
                this.setCurrentUser(user);
            }
            return user;
        } catch (err) {
            this.logout();
            throw err;
        }
    }

    async changePassword(passwordActual, passwordNueva) {
        return this.request('/auth/change-password', {
            method: 'POST',
            body: JSON.stringify({
                password_actual: passwordActual,
                password_nueva: passwordNueva
            })
        });
    }

    async getUsers() {
        return this.request('/auth/users');
    }

    async createUser(userData) {
        return this.request('/auth/users', {
            method: 'POST',
            body: JSON.stringify(userData)
        });
    }

    async deleteUser(userId) {
        return this.request(`/auth/users/${userId}`, {
            method: 'DELETE'
        });
    }

    async updateUser(userId, data) {
        return this.request(`/auth/users/${userId}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    // Contractors
    async getContractors(query = '') {
        const q = query ? `?query=${encodeURIComponent(query)}` : '';
        return this.request(`/contractors${q}`);
    }

    async getContractor(id) {
        return this.request(`/contractors/${id}`);
    }

    async createContractor(data) {
        return this.request('/contractors', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    async updateContractor(id, data) {
        return this.request(`/contractors/${id}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    async deleteContractor(id) {
        return this.request(`/contractors/${id}`, {
            method: 'DELETE'
        });
    }

    async deactivateContractor(id) {
        return this.request(`/contractors/${id}/deactivate`, {
            method: 'PATCH'
        });
    }

    async getContractorMissingFields(id) {
        return this.request(`/contractors/${id}/missing-fields`);
    }

    async enrichContractorFromDocs(id, documentIds = [], manualData = null) {
        return this.request(`/contractors/${id}/enrich-from-docs`, {
            method: 'POST',
            body: JSON.stringify({
                document_ids: documentIds,
                manual_data: manualData
            })
        });
    }

    async updateContractorFromRut(id, file) {
        const formData = new FormData();
        formData.append('file', file);
        return this.request(`/contractors/${id}/update-from-rut`, {
            method: 'POST',
            body: formData,
            isFormData: true
        });
    }

    async parseRutDocument(file) {
        const formData = new FormData();
        formData.append('file', file);
        return this.request('/contractors/parse-rut', {
            method: 'POST',
            body: formData,
            isFormData: true
        });
    }

    // Contracts
    async getContracts(params = {}) {
        const queryParams = new URLSearchParams();
        if (params.tipologia) queryParams.append('tipologia', params.tipologia);
        if (params.estado) queryParams.append('estado', params.estado);
        if (params.query) queryParams.append('query', params.query);
        if (params.vigencia) queryParams.append('vigencia', params.vigencia);
        const qStr = queryParams.toString() ? `?${queryParams.toString()}` : '';
        return this.request(`/contracts${qStr}`);
    }

    // Vigencias & Eras de Contratación
    async getVigencias() {
        return this.request('/contracts/vigencias');
    }

    async createVigencia(data) {
        return this.request('/contracts/vigencias', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    async activateVigencia(year) {
        return this.request(`/contracts/vigencias/${year}/activate`, {
            method: 'PATCH'
        });
    }

    async getNextContractNumber(vigencia, tipologia = '') {
        const q = new URLSearchParams({ vigencia });
        if (tipologia) q.append('tipologia', tipologia);
        return this.request(`/contracts/next-number?${q.toString()}`);
    }

    async getContract(id) {
        return this.request(`/contracts/${id}`);
    }

    async createContract(data) {
        return this.request('/contracts', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    async updateContract(id, data) {
        return this.request(`/contracts/${id}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    async updateContractStatus(id, nuevo_estado, observacion = '') {
        return this.request(`/contracts/${id}/status`, {
            method: 'PATCH',
            body: JSON.stringify({ nuevo_estado, observacion })
        });
    }

    async updateContractAddition(id, adicion_1, prorroga_1 = null) {
        return this.request(`/contracts/${id}/adicion`, {
            method: 'PATCH',
            body: JSON.stringify({ adicion_1, prorroga_1 })
        });
    }

    async updateContractObjeto(id, objeto) {
        return this.request(`/contracts/${id}/objeto`, {
            method: 'PATCH',
            body: JSON.stringify({ objeto })
        });
    }

    async updateContractNumber(id, nuevo_numero, forzar_prefijo = true) {
        return this.request(`/contracts/${id}/numero`, {
            method: 'PATCH',
            body: JSON.stringify({ nuevo_numero, forzar_prefijo })
        });
    }

    async refreshContractNecesidad(id, data = {}) {
        return this.request(`/contracts/${id}/refresh-necesidad`, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    async refreshContractAllSections(id, data = {}) {
        return this.request(`/contracts/${id}/refresh-all-sections`, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    async batchRefreshNecesidades(data = {}) {
        return this.request('/contracts/batch-refresh-necesidades', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    async deleteContract(id, motivo = '') {
        return this.request(`/contracts/${id}`, {
            method: 'DELETE',
            body: motivo ? JSON.stringify({ motivo: motivo }) : null
        });
    }

    async getTypologiesCatalog() {
        return this.request('/contracts/catalogs/typologies');
    }

    async getModalitiesCatalog() {
        return this.request('/contracts/catalogs/modalities');
    }

    // Documents
    async uploadDocument(file, contratoId = null, contratistaId = null, tipoDocumento = 'PROPUESTA') {
        const formData = new FormData();
        formData.append('file', file);
        if (contratoId) formData.append('contrato_id', contratoId);
        if (contratistaId) formData.append('contratista_id', contratistaId);
        formData.append('tipo_documento', tipoDocumento);
        formData.append('categoria', 'SOPORTE_CONTRATISTA');

        return this.request('/documents/upload', {
            method: 'POST',
            body: formData,
            isFormData: true
        });
    }

    async uploadMultipleDocuments(files, contratoId = null, contratistaId = null) {
        const formData = new FormData();
        for (const file of files) {
            formData.append('files', file);
        }
        if (contratoId) formData.append('contrato_id', contratoId);
        if (contratistaId) formData.append('contratista_id', contratistaId);

        return this.request('/documents/upload-multiple', {
            method: 'POST',
            body: formData,
            isFormData: true
        });
    }

    async getDocuments(contratoId = null, contratistaId = null) {
        const params = new URLSearchParams();
        if (contratoId) params.append('contrato_id', contratoId);
        if (contratistaId) params.append('contratista_id', contratistaId);
        const q = params.toString() ? `?${params.toString()}` : '';
        return this.request(`/documents${q}`);
    }

    // Agents & AI
    async extractDocumentData(documentId) {
        return this.request(`/agents/extract-document/${documentId}`, {
            method: 'POST'
        });
    }

    async extractMultipleDocuments(documentIds) {
        return this.request('/agents/extract-multiple-documents', {
            method: 'POST',
            body: JSON.stringify({ document_ids: documentIds })
        });
    }

    async createContractorFromDoc(documentId) {
        return this.request(`/agents/create-contractor-from-doc/${documentId}`, {
            method: 'POST'
        });
    }

    async createContractorFromMultipleDocs(documentIds, contratistaData = null) {
        return this.request('/agents/create-contractor-from-docs', {
            method: 'POST',
            body: JSON.stringify({ 
                document_ids: documentIds,
                contratista_data: contratistaData
            })
        });
    }

    async draftWithAgent(data) {
        return this.request('/agents/draft', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    async generateJustificacion(data) {
        return this.request('/agents/generate-justificacion', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    async buildNecesidad(data) {
        return this.request('/agents/build-necesidad', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    async generateObjetivos(data) {
        return this.request('/agents/generate-objetivos', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    async generateObligaciones(data) {
        return this.request('/agents/generate-obligaciones', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }


    async generateObjeto(data) {
        return this.request('/agents/generate-objeto', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    async generateRiskMatrix(data) {
        return this.request('/agents/generate-risk-matrix', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    async downloadRiskMatrixDocx(data) {
        const headers = {
            'Content-Type': 'application/json'
        };
        if (this.token) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }
        const response = await fetch(`${API_BASE}/agents/generate-risk-matrix-docx`, {
            method: 'POST',
            headers: headers,
            body: JSON.stringify(data)
        });
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || 'Error al descargar la matriz de riesgos en Word.');
        }
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const filename = `Matriz_Riesgos_ESPY_${(data.objeto || 'Contractual').substring(0, 30).replace(/[^a-zA-Z0-9]/g, '_')}.docx`;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => window.URL.revokeObjectURL(url), 2000);
        return true;
    }

    async downloadRiskMatrixPdf(data) {
        const headers = {
            'Content-Type': 'application/json'
        };
        if (this.token) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }
        const response = await fetch(`${API_BASE}/agents/generate-risk-matrix-pdf`, {
            method: 'POST',
            headers: headers,
            body: JSON.stringify(data)
        });
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || 'Error al descargar la matriz de riesgos en PDF.');
        }
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const filename = `Matriz_Riesgos_ESPY_${(data.objeto || 'Contractual').substring(0, 30).replace(/[^a-zA-Z0-9]/g, '_')}.pdf`;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => window.URL.revokeObjectURL(url), 2000);
        return true;
    }

    async uploadLetterheadLogo(file) {
        const formData = new FormData();
        formData.append('file', file);
        const headers = {};
        if (this.token) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }
        const response = await fetch(`${API_BASE}/agents/upload-letterhead-logo`, {
            method: 'POST',
            headers: headers,
            body: formData
        });
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || 'Error al subir la imagen del membrete.');
        }
        return await response.json();
    }

    async uploadAndParseRiskDocument(file, contratoId = null) {
        const formData = new FormData();
        formData.append('file', file);
        if (contratoId) formData.append('contrato_id', contratoId);
        return this.request('/agents/upload-and-parse-risk-document', {
            method: 'POST',
            body: formData,
            isFormData: true
        });
    }

    // Templates (.docx)
    async getTemplatesStatus() {
        return this.request('/templates/status');
    }

    async getAvailableTemplates() {
        return this.request('/templates/available');
    }

    async uploadCustomTemplate(file, templateType) {
        const formData = new FormData();
        formData.append('file', file);
        return this.request(`/templates/upload/${templateType}`, {
            method: 'POST',
            body: formData,
            isFormData: true
        });
    }

    async resetCustomTemplate(templateType) {
        return this.request(`/templates/reset/${templateType}`, {
            method: 'POST'
        });
    }

    getActiveTemplateDownloadUrl(templateType) {
        const tokenParam = this.token ? `?token=${encodeURIComponent(this.token)}` : '';
        return `${API_BASE}/templates/download-active/${templateType}${tokenParam}`;
    }

    async generateDocument(contractId, templateType) {
        return this.request(`/templates/generate/${contractId}/${templateType}`, {
            method: 'POST'
        });
    }

    getTemplateDownloadUrl(contractId, templateType) {
        const tokenParam = this.token ? `?token=${encodeURIComponent(this.token)}` : '';
        return `${API_BASE}/templates/download/${contractId}/${templateType}${tokenParam}`;
    }

    // Excel Matrix
    async syncContractToExcel(contractId) {
        return this.request(`/excel/sync/${contractId}`, {
            method: 'POST'
        });
    }

    async deleteContractFromExcel(contractId) {
        return this.request(`/excel/contract/${contractId}`, {
            method: 'DELETE'
        });
    }

    async syncAllToExcel() {
        return this.request('/excel/sync-all', {
            method: 'POST'
        });
    }

    getExcelDownloadUrl(vigencia = null) {
        const queryParams = new URLSearchParams();
        if (vigencia && vigencia !== 'ALL') {
            queryParams.append('vigencia', vigencia);
        }
        if (this.token) {
            queryParams.append('token', this.token);
        }
        const qs = queryParams.toString() ? `?${queryParams.toString()}` : '';
        return `${API_BASE}/excel/download${qs}`;
    }

    // =========================================================
    // EJECUCIÓN CONTRACTUAL Y COMPROBANTES DE EGRESO
    // =========================================================
    async getExecutionSummary(vigencia = null) {
        const q = vigencia ? `?vigencia=${encodeURIComponent(vigencia)}` : '';
        return this.request(`/execution/summary${q}`);
    }

    async getExecutionContractors(params = {}) {
        const queryParams = new URLSearchParams();
        if (params.query) queryParams.append('query', params.query);
        if (params.vigencia) queryParams.append('vigencia', params.vigencia);
        const qs = queryParams.toString() ? `?${queryParams.toString()}` : '';
        return this.request(`/execution/contractors${qs}`);
    }

    async getExecutionContractor(id, vigencia = null) {
        const q = vigencia ? `?vigencia=${encodeURIComponent(vigencia)}` : '';
        return this.request(`/execution/contractors/${id}${q}`);
    }

    async getExecutionContracts(params = {}) {
        const queryParams = new URLSearchParams();
        if (params.query) queryParams.append('query', params.query);
        if (params.vigencia) queryParams.append('vigencia', params.vigencia);
        if (params.contractor_id) queryParams.append('contractor_id', params.contractor_id);
        const qs = queryParams.toString() ? `?${queryParams.toString()}` : '';
        return this.request(`/execution/contracts${qs}`);
    }

    async getExecutionContract(contractId) {
        return this.request(`/execution/contracts/${contractId}`);
    }

    async getPayments(params = {}) {
        const queryParams = new URLSearchParams();
        if (params.query) queryParams.append('query', params.query);
        if (params.vigencia) queryParams.append('vigencia', params.vigencia);
        if (params.contractor_id) queryParams.append('contractor_id', params.contractor_id);
        if (params.contract_id) queryParams.append('contract_id', params.contract_id);
        if (params.rubro) queryParams.append('rubro', params.rubro);
        if (params.limit) queryParams.append('limit', params.limit);
        if (params.offset) queryParams.append('offset', params.offset);
        const qs = queryParams.toString() ? `?${queryParams.toString()}` : '';
        return this.request(`/execution/payments${qs}`);
    }

    async getPayment(id) {
        return this.request(`/execution/payments/${id}`);
    }

    async createPayment(data) {
        return this.request('/execution/payments', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    async updatePayment(id, data) {
        return this.request(`/execution/payments/${id}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    async deletePayment(id) {
        return this.request(`/execution/payments/${id}`, {
            method: 'DELETE'
        });
    }

    async reassignPayment(id, payload) {
        return this.request(`/execution/payments/${id}/reassign`, {
            method: 'PATCH',
            body: JSON.stringify(payload)
        });
    }

    async importPayments(formData) {
        return this.request('/execution/import', {
            method: 'POST',
            body: formData,
            isFormData: true
        });
    }

    async importPdfPaymentPackets(formData) {
        return this.request('/execution/import-pdf-packets', {
            method: 'POST',
            body: formData,
            isFormData: true
        });
    }

    getExecutionExportUrl(vigencia = null) {
        const queryParams = new URLSearchParams();
        if (vigencia && vigencia !== 'ALL') {
            queryParams.append('vigencia', vigencia);
        }
        if (this.token) {
            queryParams.append('token', this.token);
        }
        const qs = queryParams.toString() ? `?${queryParams.toString()}` : '';
        return `${API_BASE}/execution/export${qs}`;
    }

    // Centro de Reportes e Informes
    async getReportsPreview(vigencia = '2026', periodo = 'ACUMULADO') {
        const queryParams = new URLSearchParams();
        if (vigencia) queryParams.append('vigencia', vigencia);
        if (periodo) queryParams.append('periodo', periodo);
        return this.request(`/reports/preview?${queryParams.toString()}`);
    }

    getReportWordDownloadUrl(vigencia = '2026', periodo = 'ACUMULADO', includeAnnexes = true) {
        const queryParams = new URLSearchParams({
            vigencia: vigencia || '2026',
            periodo: periodo || 'ACUMULADO',
            include_annexes: includeAnnexes ? 'true' : 'false'
        });
        if (this.token) {
            queryParams.append('token', this.token);
        }
        return `${API_BASE}/reports/download/word?${queryParams.toString()}`;
    }

    getReportPowerPointDownloadUrl(vigencia = '2026', periodo = 'ACUMULADO', includeAnnexes = true) {
        const queryParams = new URLSearchParams({
            vigencia: vigencia || '2026',
            periodo: periodo || 'ACUMULADO',
            include_annexes: includeAnnexes ? 'true' : 'false'
        });
        if (this.token) {
            queryParams.append('token', this.token);
        }
        return `${API_BASE}/reports/download/powerpoint?${queryParams.toString()}`;
    }

    // Información de red y enlaces de acceso
    async getNetworkInfo() {
        return this.request('/system/network-info');
    }

    // Configuración segura de Gemini API Key en el Servidor
    async getConfigStatus() {
        return this.request('/system/config-status');
    }

    async configureApiKey(apiKey) {
        return this.request('/system/config-api-key', {
            method: 'POST',
            body: JSON.stringify({ api_key: apiKey })
        });
    }

    // =========================================================================
    // APU Y EVALUACIÓN COMPARATIVA
    // =========================================================================
    async getApuDemoCase() {
        return this.request('/apu/demo-case');
    }

    async extractOfferFromFile(file) {
        const formData = new FormData();
        formData.append('file', file);
        return this.request('/apu/extract-offer', {
            method: 'POST',
            body: formData,
            isFormData: true
        });
    }

    async extractMultipleOffers(files) {
        const formData = new FormData();
        for (let i = 0; i < files.length; i++) {
            formData.append('files', files[i]);
        }
        return this.request('/apu/extract-multiple-offers', {
            method: 'POST',
            body: formData,
            isFormData: true
        });
    }

    async calculateRules(data) {
        return this.request('/apu/calculate-rules', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    async evaluateApuProposals(payload) {
        return this.request('/apu/evaluate', {
            method: 'POST',
            body: JSON.stringify(payload)
        });
    }

    async decomposeApuItem(item, contextoObjeto = '') {
        return this.request('/apu/decompose-item', {
            method: 'POST',
            body: JSON.stringify({ item: item, contexto_objeto: contextoObjeto })
        });
    }

    async downloadInformeEvaluacionDocx(payload) {
        const token = this.getToken();
        const headers = { 'Content-Type': 'application/json' };
        if (token) headers['Authorization'] = `Bearer ${token}`;
        const response = await fetch(`${API_BASE}/apu/generate-informe-docx`, {
            method: 'POST',
            headers: headers,
            body: JSON.stringify(payload)
        });
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || 'Error al descargar el Informe de Evaluación en Word.');
        }
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `Informe_Evaluacion_Comparativa_${Date.now()}.docx`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        return true;
    }

    async downloadPresupuestoApuDocx(payload) {
        const token = this.getToken();
        const headers = { 'Content-Type': 'application/json' };
        if (token) headers['Authorization'] = `Bearer ${token}`;
        const response = await fetch(`${API_BASE}/apu/generate-presupuesto-apu-docx`, {
            method: 'POST',
            headers: headers,
            body: JSON.stringify(payload)
        });
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || 'Error al descargar el Presupuesto y APU en Word.');
        }
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `APU_Presupuesto_Precontractual_${Date.now()}.docx`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        return true;
    }

    async saveContractEstudioMercado(contractId, payload) {
        return this.request(`/contracts/${contractId}/estudio-mercado`, {
            method: 'POST',
            body: JSON.stringify(payload)
        });
    }

    async deleteContractEstudioMercado(contractId) {
        return this.request(`/contracts/${contractId}/estudio-mercado`, {
            method: 'DELETE'
        });
    }

    async getContractEstudioMercado(contractId) {
        return this.request(`/contracts/${contractId}/estudio-mercado`, {
            method: 'GET'
        });
    }

    // =========================================================================
    // AGENTE CLASIFICADOR UNSPSC
    // =========================================================================
    async getUnspscStatus() {
        return this.request('/unspsc/status');
    }

    async searchUnspsc(query, limit = 50) {
        const q = encodeURIComponent(query || '');
        return this.request(`/unspsc/search?query=${q}&limit=${limit}`);
    }

    async analyzeUnspsc(payload) {
        return this.request('/unspsc/analyze', {
            method: 'POST',
            body: JSON.stringify(payload)
        });
    }

    async analyzeUnspscFiles(formData) {
        return this.request('/unspsc/analyze-files', {
            method: 'POST',
            body: formData,
            isFormData: true
        });
    }

    async saveContractUnspsc(contractId, payload) {
        return this.request(`/unspsc/contracts/${contractId}/save`, {
            method: 'POST',
            body: JSON.stringify(payload)
        });
    }

    async getContractUnspsc(contractId) {
        return this.request(`/unspsc/contracts/${contractId}`);
    }

    async downloadUnspscReportDocx(payload) {
        const token = this.getToken();
        const headers = { 'Content-Type': 'application/json' };
        if (token) headers['Authorization'] = `Bearer ${token}`;
        const response = await fetch(`${API_BASE}/unspsc/export-docx`, {
            method: 'POST',
            headers: headers,
            body: JSON.stringify(payload)
        });
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || 'Error al descargar el dictamen UNSPSC en Word.');
        }
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const num = (payload.numero_contrato || 'Proceso_UNSPSC').replace(/[\/\\]/g, '_');
        a.download = `Dictamen_UNSPSC_${num}_${Date.now()}.docx`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        return true;
    }

    async getCdpMarcasCorte() {
        return this.request('/cdp/marcas-corte');
    }
}



window.api = new ApiClient();
