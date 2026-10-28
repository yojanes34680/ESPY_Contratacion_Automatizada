"""
Contractor Data Enrichment Service.
Módulo especializado para la completitud, actualización no destructiva y enriquecimiento
de información fiscal, de contacto y bancaria de contratistas existentes a partir
de expedientes documentales (RUT, propuestas, cédulas, certificaciones bancarias).
"""
import re
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.contractor import Contratista, TipoPersona, TipoDocumento, RegimenTributario
from app.models.document import Documento
from app.models.audit_log import Auditoria
from app.services.document_parser import parse_document_text
from app.services.rut_parser import parse_dian_rut, calculate_dian_dv
from app.services.gemini_client import gemini_service
from app.utils.logger import logger

PLACEHOLDER_VALUES = {
    "sin dirección", "sin direccion", "colombia", "bogotá d.c.", "bogota d.c.", "cundinamarca",
    "no registrado", "no registrada", "por definir", "sin registrar", "no aplica", ""
}

def is_empty_or_placeholder(value: Optional[str]) -> bool:
    """Verifica si un campo textual está vacío o contiene un valor comodín genérico."""
    if value is None:
        return True
    val_clean = str(value).strip().lower()
    return val_clean == "" or val_clean in PLACEHOLDER_VALUES

def get_missing_contractor_fields(contractor: Contratista) -> List[Dict[str, str]]:
    """
    Evalúa la ficha del contratista y devuelve un listado estructurado de los campos
    esenciales que hacen falta o requieren actualización.
    """
    missing: List[Dict[str, str]] = []

    # 1. Teléfono / Celular
    if is_empty_or_placeholder(contractor.telefono) or len(re.sub(r"[^\d]", "", str(contractor.telefono))) < 7:
        missing.append({
            "key": "telefono",
            "label": "Número Celular / Teléfono",
            "categoria": "contacto",
            "icon": "📞"
        })

    # 2. Correo Electrónico
    if is_empty_or_placeholder(contractor.correo_electronico) or "@" not in str(contractor.correo_electronico):
        missing.append({
            "key": "correo_electronico",
            "label": "Correo Electrónico",
            "categoria": "contacto",
            "icon": "✉️"
        })

    # 3. Dirección Principal
    if is_empty_or_placeholder(contractor.direccion) or len(str(contractor.direccion).strip()) < 5:
        missing.append({
            "key": "direccion",
            "label": "Dirección Principal",
            "categoria": "ubicacion",
            "icon": "📍"
        })

    # 4. Municipio
    if is_empty_or_placeholder(contractor.municipio):
        missing.append({
            "key": "municipio",
            "label": "Municipio / Ciudad",
            "categoria": "ubicacion",
            "icon": "🏙️"
        })

    # 5. Información Bancaria
    if is_empty_or_placeholder(contractor.banco_numero_cuenta):
        missing.append({
            "key": "banco_numero_cuenta",
            "label": "Información Bancaria (Banco y Número de Cuenta)",
            "categoria": "bancaria",
            "icon": "🏦"
        })

    # 6. Representante Legal (Solo para empresas / personas jurídicas)
    if contractor.tipo_persona == TipoPersona.JURIDICA:
        if is_empty_or_placeholder(contractor.representante_legal_nombre):
            missing.append({
                "key": "representante_legal_nombre",
                "label": "Nombre del Representante Legal",
                "categoria": "legal",
                "icon": "👔"
            })
        if is_empty_or_placeholder(contractor.representante_legal_documento):
            missing.append({
                "key": "representante_legal_documento",
                "label": "Cédula del Representante Legal",
                "categoria": "legal",
                "icon": "🪪"
            })

    # 7. Dígito de Verificación (Solo para empresas / NIT)
    if contractor.tipo_persona == TipoPersona.JURIDICA:
        if not contractor.digito_verificacion:
            missing.append({
                "key": "digito_verificacion",
                "label": "Dígito de Verificación (DV)",
                "categoria": "tributaria",
                "icon": "🔢"
            })

    return missing

def enrich_contractor(
    contractor: Contratista, 
    data: Dict[str, Any], 
    db: Session, 
    source_desc: str = "Documentación Suministrada"
) -> Dict[str, Any]:
    """
    Aplica una actualización inteligente y no destructiva sobre la ficha del contratista.
    Solo completa o enriquece campos faltantes o genéricos, preservando datos válidos preexistentes
    a menos que el dato nuevo aporte mayor especificidad o proceda de una fuente oficial (RUT).
    """
    updated_fields: List[str] = []

    # 0. Tipo de Persona y Documento
    new_tipo_per = data.get("tipo_persona")
    if new_tipo_per:
        norm_tp = "JURIDICA" if ("JURIDICA" in str(new_tipo_per).upper() or "EMPRESA" in str(new_tipo_per).upper()) else "NATURAL"
        if getattr(contractor.tipo_persona, "value", str(contractor.tipo_persona)) != norm_tp:
            contractor.tipo_persona = TipoPersona(norm_tp)
            updated_fields.append("tipo_persona")

    # Si es Persona Natural, asegurar que la cédula esté limpia sin DV y no lleve representante legal
    if contractor.tipo_persona == TipoPersona.NATURAL:
        if contractor.tipo_documento != TipoDocumento.CC and not data.get("tipo_documento"):
            contractor.tipo_documento = TipoDocumento.CC
            updated_fields.append("tipo_documento")
        if contractor.numero_documento and "-" in contractor.numero_documento:
            contractor.numero_documento = re.sub(r"-\d+$", "", contractor.numero_documento).strip()
            updated_fields.append("numero_documento")
        if contractor.digito_verificacion:
            contractor.digito_verificacion = None
            updated_fields.append("digito_verificacion")
        contractor.representante_legal_nombre = None
        contractor.representante_legal_documento = None
    else:
        # Empresa (JURIDICA)
        if contractor.tipo_documento != TipoDocumento.NIT:
            contractor.tipo_documento = TipoDocumento.NIT
            updated_fields.append("tipo_documento")

    # 1. Teléfono / Celular
    new_tel = data.get("telefono") or data.get("celular")
    if new_tel:
        clean_tel = re.sub(r"[^\d]", "", str(new_tel))
        if len(clean_tel) >= 7:
            if is_empty_or_placeholder(contractor.telefono) or (contractor.telefono != clean_tel and len(clean_tel) == 10):
                contractor.telefono = clean_tel
                updated_fields.append("telefono")

    # 2. Correo Electrónico
    new_email = data.get("correo_electronico") or data.get("email") or data.get("correo")
    if new_email and "@" in str(new_email):
        clean_email = str(new_email).strip().lower()
        if not any(k in clean_email for k in ["dian.gov", "yolombo.gov", "serviciospublicosyol"]):
            if is_empty_or_placeholder(contractor.correo_electronico) or contractor.correo_electronico != clean_email:
                contractor.correo_electronico = clean_email
                updated_fields.append("correo_electronico")

    # 3. Dirección Principal
    new_dir = data.get("direccion")
    if new_dir and not is_empty_or_placeholder(new_dir):
        clean_dir = str(new_dir).strip()
        if len(clean_dir) >= 4:
            if is_empty_or_placeholder(contractor.direccion) or contractor.direccion in ("Sin dirección", "No registrada"):
                contractor.direccion = clean_dir
                updated_fields.append("direccion")

    # 4. Municipio
    new_mun = data.get("municipio") or data.get("ciudad")
    if new_mun and not is_empty_or_placeholder(new_mun):
        clean_mun = str(new_mun).strip()
        if is_empty_or_placeholder(contractor.municipio) or contractor.municipio in ("Colombia", "Bogotá D.C."):
            contractor.municipio = clean_mun
            updated_fields.append("municipio")

    # 5. Departamento
    new_dep = data.get("departamento")
    if new_dep and not is_empty_or_placeholder(new_dep):
        clean_dep = str(new_dep).strip()
        if is_empty_or_placeholder(contractor.departamento) or contractor.departamento in ("Colombia", "Cundinamarca"):
            contractor.departamento = clean_dep
            updated_fields.append("departamento")

    # 6. Dígito de Verificación (DV) - Solo para empresas (JURIDICA)
    if contractor.tipo_persona == TipoPersona.JURIDICA:
        new_dv = data.get("digito_verificacion")
        if not new_dv and contractor.numero_documento:
            clean_nit = re.sub(r"-\d+$", "", str(contractor.numero_documento)).strip()
            new_dv = calculate_dian_dv(clean_nit)
        if new_dv and (not contractor.digito_verificacion or str(contractor.digito_verificacion) != str(new_dv)):
            contractor.digito_verificacion = str(new_dv).strip()
            updated_fields.append("digito_verificacion")

        # 7. Representante Legal (Nombre y Cédula)
        from app.services.document_parser import is_valid_person_name
        new_rep_nom = data.get("representante_legal_nombre")
        if new_rep_nom and not is_empty_or_placeholder(new_rep_nom):
            clean_rn = str(new_rep_nom).strip().upper()
            if is_valid_person_name(clean_rn):
                if is_empty_or_placeholder(contractor.representante_legal_nombre) or contractor.representante_legal_nombre != clean_rn:
                    contractor.representante_legal_nombre = clean_rn
                    updated_fields.append("representante_legal_nombre")

        new_rep_doc = data.get("representante_legal_documento")
        if new_rep_doc and not is_empty_or_placeholder(new_rep_doc):
            clean_rd = re.sub(r"[^\d]", "", str(new_rep_doc))
            clean_rd = re.sub(r"-\d+$", "", clean_rd).strip()
            # Prohibir copiar NIT como cédula del representante legal
            nit_comp = str(contractor.numero_documento or "").strip()
            is_nit_clone = (clean_rd == nit_comp) or (clean_rd.startswith(("800", "811", "830", "860", "890", "900", "901", "902")) and len(clean_rd) >= 8)
            if clean_rd and not is_nit_clone and (is_empty_or_placeholder(contractor.representante_legal_documento) or contractor.representante_legal_documento != clean_rd):
                contractor.representante_legal_documento = clean_rd
                updated_fields.append("representante_legal_documento")

    # 8. Régimen Tributario
    new_reg = data.get("regimen_tributario")
    if new_reg:
        try:
            if isinstance(new_reg, str) and new_reg in RegimenTributario.__members__:
                enum_reg = RegimenTributario[new_reg]
                if not contractor.regimen_tributario or contractor.regimen_tributario != enum_reg:
                    contractor.regimen_tributario = enum_reg
                    updated_fields.append("regimen_tributario")
        except Exception:
            pass

    # 9. Datos Bancarios
    new_banco = data.get("banco_nombre") or data.get("banco")
    if new_banco and not is_empty_or_placeholder(new_banco):
        if is_empty_or_placeholder(contractor.banco_nombre):
            contractor.banco_nombre = str(new_banco).strip()
            updated_fields.append("banco_nombre")

    new_banco_tipo = data.get("banco_tipo_cuenta") or data.get("tipo_cuenta")
    if new_banco_tipo and not is_empty_or_placeholder(new_banco_tipo):
        if is_empty_or_placeholder(contractor.banco_tipo_cuenta):
            contractor.banco_tipo_cuenta = str(new_banco_tipo).strip()
            updated_fields.append("banco_tipo_cuenta")

    new_banco_num = data.get("banco_numero_cuenta") or data.get("numero_cuenta") or data.get("cuenta_bancaria")
    if new_banco_num and not is_empty_or_placeholder(new_banco_num):
        clean_acc = str(new_banco_num).strip()
        if is_empty_or_placeholder(contractor.banco_numero_cuenta):
            contractor.banco_numero_cuenta = clean_acc
            updated_fields.append("banco_numero_cuenta")

    # 10. Resumen de Perfil / Experiencia
    new_perfil = data.get("perfil_profesional_resumen") or data.get("perfil_o_experiencia_resumen")
    if new_perfil and not is_empty_or_placeholder(new_perfil):
        if is_empty_or_placeholder(contractor.perfil_o_experiencia_resumen):
            contractor.perfil_o_experiencia_resumen = str(new_perfil).strip()
            updated_fields.append("perfil_o_experiencia_resumen")

    # 11. Nombre o Razón Social (solo si era placeholder)
    new_nombre = data.get("nombre_o_razon_social")
    if new_nombre and not is_empty_or_placeholder(new_nombre) and new_nombre != "Contratista Identificado":
        if is_empty_or_placeholder(contractor.nombre_o_razon_social) or contractor.nombre_o_razon_social == "Contratista Identificado":
            contractor.nombre_o_razon_social = str(new_nombre).strip().upper()
            updated_fields.append("nombre_o_razon_social")

    if updated_fields:
        audit = Auditoria(
            contrato_id=None,
            accion="ENRIQUECIMIENTO_CONTRATISTA",
            detalle=f"Actualizados campos ({', '.join(updated_fields)}) para contratista '{contractor.nombre_o_razon_social}' (ID {contractor.id}) desde {source_desc}.",
            usuario="Sistema de Extracción / Enriquecimiento IA"
        )
        db.add(audit)
        db.commit()
        db.refresh(contractor)
        logger.info(f"Contratista ID {contractor.id} enriquecido con campos: {', '.join(updated_fields)}")

    remaining_missing = get_missing_contractor_fields(contractor)
    return {
        "contractor_id": contractor.id,
        "nombre_o_razon_social": contractor.nombre_o_razon_social,
        "campos_actualizados": updated_fields,
        "total_actualizados": len(updated_fields),
        "campos_faltantes_restantes": remaining_missing,
        "completo": len(remaining_missing) == 0
    }

def extract_and_enrich_from_docs(
    contractor: Contratista, 
    document_ids: List[int], 
    db: Session, 
    manual_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Extrae texto e información estructurada de un conjunto de documentos vinculados,
    combina las fuentes (RUT DIAN determinista + propuestas/contratos) y aplica el
    enriquecimiento automático sobre el contratista.
    """
    from app.config import settings

    consolidated_info: Dict[str, Any] = {}
    docs_processed: List[Dict[str, Any]] = []

    for doc_id in document_ids:
        doc = db.query(Documento).filter(Documento.id == doc_id).first()
        if not doc:
            continue

        # Asegurar vinculación formal del documento con el contratista
        if doc.contratista_id != contractor.id:
            doc.contratista_id = contractor.id
            db.commit()

        full_path = settings.BASE_DIR / doc.ruta_relativa
        if not full_path.exists():
            continue

        try:
            raw_text = parse_document_text(full_path)
            if not raw_text or not raw_text.strip():
                continue

            # 1. Extracción de RUT con el parser universal determinista
            rut_info = parse_dian_rut(raw_text)
            if rut_info:
                for k, v in rut_info.items():
                    if v and not is_empty_or_placeholder(v):
                        consolidated_info[k] = v

            # 1.5 Extracción de Cédula de Ciudadanía (Formato A Digital y Formato B Amarilla)
            try:
                from app.services.document_parser import extract_colombian_cedula_data
                ced_info = extract_colombian_cedula_data(raw_text)
                if ced_info.get("nombre_completo"):
                    # Si el contratista es persona natural, llena su nombre
                    if contractor.tipo_persona == TipoPersona.NATURAL:
                        if "nombre_o_razon_social" not in consolidated_info or is_empty_or_placeholder(consolidated_info.get("nombre_o_razon_social")):
                            consolidated_info["nombre_o_razon_social"] = ced_info["nombre_completo"]
                    # Siempre llena representante_legal_nombre para personas jurídicas
                    if "representante_legal_nombre" not in consolidated_info or is_empty_or_placeholder(consolidated_info.get("representante_legal_nombre")):
                        consolidated_info["representante_legal_nombre"] = ced_info["nombre_completo"]

                if ced_info.get("numero_documento"):
                    if contractor.tipo_persona == TipoPersona.NATURAL:
                        if "numero_documento" not in consolidated_info or is_empty_or_placeholder(consolidated_info.get("numero_documento")):
                            consolidated_info["numero_documento"] = ced_info["numero_documento"]
                            consolidated_info["tipo_documento"] = "CC"
                    if "representante_legal_documento" not in consolidated_info or is_empty_or_placeholder(consolidated_info.get("representante_legal_documento")):
                        consolidated_info["representante_legal_documento"] = ced_info["numero_documento"]
            except Exception as e_ced:
                logger.debug(f"Aviso en parseo de cédula para doc {doc_id}: {e_ced}")

            # 2. Extracción mediante Gemini / OCR heurístico
            try:
                ai_extracted = gemini_service.extract_contractor_data(raw_text)
                ai_dict = ai_extracted.model_dump()
                for k, v in ai_dict.items():
                    if v and not is_empty_or_placeholder(v):
                        # Dar prioridad al RUT en datos tributarios/civiles y a la propuesta en bancos
                        if k not in consolidated_info or k in ("banco_nombre", "banco_tipo_cuenta", "banco_numero_cuenta", "perfil_profesional_resumen"):
                            consolidated_info[k] = v
                
                doc.datos_extraidos_json = ai_dict
                db.commit()
            except Exception as e_ai:
                logger.debug(f"Aviso en extracción IA para doc {doc_id}: {e_ai}")

            docs_processed.append({
                "id": doc.id,
                "nombre_archivo": doc.nombre_archivo_original,
                "datos_detectados": list(consolidated_info.keys())
            })
        except Exception as e:
            logger.warning(f"Error procesando documento {doc_id} para enriquecimiento: {e}")

    # Si el usuario suministró datos manuales en el formulario, tienen prioridad de sobreescritura
    if manual_data:
        for k, v in manual_data.items():
            if v is not None and str(v).strip() != "":
                consolidated_info[k] = v

    # Ejecutar enriquecimiento sobre el contratista
    source_label = f"lote de {len(document_ids)} documento(s)" if document_ids else "datos suministrados"
    result = enrich_contractor(contractor, consolidated_info, db, source_desc=source_label)
    result["documentos_procesados"] = docs_processed
    return result
