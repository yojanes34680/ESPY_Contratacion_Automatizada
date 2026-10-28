"""Seed script to populate pagos_contratos with the 148 payment vouchers and their retenciones."""
import csv
import io
import re
import sys
from pathlib import Path
from datetime import datetime

backend_dir = Path(__file__).resolve().parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy.orm import Session
from app.database import SessionLocal, engine, Base
from app.models.contract import Contrato
from app.models.contractor import Contratista
from app.models.execution import PagoContrato
from app.utils.logger import logger

RAW_PAYMENTS_DATA = """Código del Contrato,Código del Egreso,Fecha de Expedición,Nombre del Beneficiario,Rubro Egreso,Total Orden,Total Retención,Total a Pagar,Nombre retenciones,(% / Valor),Nombre retenciones,(% / Valor),Nombre retenciones,(% / Valor),Nombre retenciones,(% / Valor),Nombre retenciones,(% / Valor),Nombre retenciones,(% / Valor),Nombre retenciones,(% / Valor),Nombre retenciones,(% / Valor),Nombre retenciones,(% / Valor)
CA-013-2026,CE N° 00058,05/02/2026,PARROQUIA SAN LORENZO,2.1.2.02.02.007,8330000,199500,8130500,Iva por Servicios Gravados (15.00%: 199500.00)
CA-013-2026,CE N° 00067,09/02/2026,PARROQUIA SAN LORENZO,2.1.2.02.02.007,8330000,199500,8130500,Iva por Servicios Gravados (15.00%: 199500.00)
CA-013-2026,CE N° 00151,17/03/2026,PARROQUIA SAN LORENZO,2.1.2.02.02.007,8330000,199500,8130500,Iva por Servicios Gravados (15.00%: 199500.00)
CA-013-2026,CE N° 00192,13/04/2026,PARROQUIA SAN LORENZO,2.1.2.02.02.007,8330000,199500,8130500,Iva por Servicios Gravados (15.00%: 199500.00)
029-2026,CE N° 00046,04/02/2026,JOSE ROMUALDO MOLINA TOBON,2.3.2.02.02.009,21189568,0,21189568,Sin retenciones
029-2026,CE N° 00139,10/03/2026,JOSE ROMUALDO MOLINA TOBON,2.3.2.02.02.009,21189568,5339772,15849796,Industria y comercio ICA (0.60%: 254275.00),Estampilla Pro Cultura (2.00%: 847583.00),Estampilla Pro-Hospital (1.00%: 423791.00),Tasa Pro Deporte y Recreación (2.00%: 847583.00),Contratos de obra Pública 5 Fondo Seguridad (5.00%: 2118957.00),Estampilla pro-justicia familiar (2.00%: 847583.00)
CO-031-2026,CE N° 00154,17/03/2026,ASOCIACION DE JUNTAS DE ACCION COMUNAL,2.3.2.02.02.005,58565540,0,58565540,Sin retenciones
CO-033-2026,CE N° 00083,13/02/2026,ASOCIACION DE JUNTAS DE ACCION COMUNAL,2.3.2.02.02.005,71774687,0,71774687,Sin retenciones
CO-039-2026,CE N° 00280,28/05/2026,ASOCIACION DE JUNTAS DE ACCION COMUNAL,2.3.2.02.02.009,42873905,0,42873905,Sin retenciones
CS-014-2026,CE N° 00254,08/05/2026,ACUATUBOS LTDA.,2.3.2.02.02.005,81565,6751.30,74813.70,Industria y comercio ICA (0.60%: 1370.80),Estampilla Pro Cultura (2.00%: 1370.80),Iva Compras Gravadas (15.00%: 1953.50),Estampilla Pro-Hospital (1.00%: 685.40),Tasa Pro Deporte y Recreación (2.00%: 1370.80),Estampilla pro-justicia familiar (2.00%: 1370.80)
CS-014-2026,CE N° 00325,19/06/2026,ACUATUBOS LTDA.,2.3.2.02.02.005,5951972,492663.20,5459308.80,Estampilla Pro Cultura (2.00%: 100033.10),Iva Compras Gravadas (15.00%: 142547.30),Estampilla Pro-Hospital (1.00%: 50016.60),Tasa Pro Deporte y Recreación (2.00%: 100033.10),Estampilla pro-justicia familiar (2.00%: 100033.10)
CS-014-2026,CE N° 00326,19/06/2026,ACUATUBOS LTDA.,2.3.2.02.02.005,4495579,372113.20,4123465.80,Estampilla Pro Cultura (2.00%: 75556.00),Iva Compras Gravadas (15.00%: 107667.20),Estampilla Pro-Hospital (1.00%: 37778.00),Tasa Pro Deporte y Recreación (2.00%: 75556.00),Estampilla pro-justicia familiar (2.00%: 75556.00)
CS-015-2026,CE N° 00040,30/01/2026,WET CHEMICAL COLOMBIA S.A.S,2.3.2.02.01.003,14726250,1528312.50,13197937.50,Estampilla Pro Cultura (2.00%: 247500.00),Iva Compras Gravadas (15.00%: 352687.50),Estampilla Pro-Hospital (1.00%: 123750.00),Retención Compras 2.5 (2.50%: 309375.00),Tasa Pro Deporte y Recreación (2.00%: 247500.00),Estampilla pro-justicia familiar (2.00%: 247500.00)
CS-017-2026,CE N° 00028,22/01/2026,ASOCIACION DE JUNTAS DE ACCION COMUNAL,2.1.2.02.02.006,14000000,644000,13356000,Industria y comercio ICA (0.60%: 84000.00),Tasa Pro Deporte y Recreación (2.00%: 280000.00),Estampilla pro-justicia familiar (2.00%: 280000.00)
CS-018-2026,CE N° 00084,13/02/2026,ASOCIACION DE JUNTAS DE ACCION COMUNAL,2.1.2.02.01.003,2118000,97428,2020572,Industria y comercio ICA (0.60%: 12708.00),Tasa Pro Deporte y Recreación (2.00%: 42360.00),Estampilla pro-justicia familiar (2.00%: 42360.00)
CS-019-2026,CE N° 00080,12/02/2026,WCP INGENIERIA S.A.S,2.1.2.02.02.008,4248943,462385,3786558,Industria y comercio ICA (0.60%: 21423.20),Estampilla Pro Cultura (2.00%: 71410.80),Iva Compras Gravadas (15.00%: 101760.50),Estampilla Pro-Hospital (1.00%: 35705.40),Retención Compras 2.5 (2.50%: 89283.50),Tasa Pro Deporte y Recreación (2.00%: 71410.80),Estampilla pro-justicia familiar (2.00%: 71410.80)
CS-019-2026,CE N° 00081,12/02/2026,WCP INGENIERIA S.A.S,2.1.2.02.02.008,3944219,429223.80,3514995.20,Industria y comercio ICA (0.60%: 19886.80),Estampilla Pro Cultura (2.00%: 66289.40),Iva Compras Gravadas (15.00%: 94462.30),Estampilla Pro-Hospital (1.00%: 33144.70),Retención Compras 2.5 (2.50%: 82861.80),Tasa Pro Deporte y Recreación (2.00%: 66289.40),Estampilla pro-justicia familiar (2.00%: 66289.40)
CS-019-2026,CE N° 00090,25/02/2026,WCP INGENIERIA S.A.S,2.1.2.02.02.008,339436,29807.60,309628.40,Industria y comercio ICA (0.60%: 1711.40),Estampilla Pro Cultura (2.00%: 5704.80),Iva Compras Gravadas (15.00%: 8129.40),Estampilla Pro-Hospital (1.00%: 2852.40),Tasa Pro Deporte y Recreación (2.00%: 5704.80),Estampilla pro-justicia familiar (2.00%: 5704.80)
CS-019-2026,CE N° 00091,25/02/2026,WCP INGENIERIA S.A.S,2.1.2.02.02.008,230479,20239.50,210239.50,Industria y comercio ICA (0.60%: 1162.10),Estampilla Pro Cultura (2.00%: 3873.60),Iva Compras Gravadas (15.00%: 5519.80),Estampilla Pro-Hospital (1.00%: 1936.80),Tasa Pro Deporte y Recreación (2.00%: 3873.60),Estampilla pro-justicia familiar (2.00%: 3873.60)
CS-019-2026,CE N° 00092,25/02/2026,WCP INGENIERIA S.A.S,2.1.2.02.02.008,171051,15020.90,156030.10,Industria y comercio ICA (0.60%: 862.40),Estampilla Pro Cultura (2.00%: 2874.80),Iva Compras Gravadas (15.00%: 4096.70),Estampilla Pro-Hospital (1.00%: 1437.40),Tasa Pro Deporte y Recreación (2.00%: 2874.80),Estampilla pro-justicia familiar (2.00%: 2874.80)
CS-019-2026,CE N° 00217,30/04/2026,WCP INGENIERIA S.A.S,2.1.2.01.002,491660,43175.20,448484.80,Industria y comercio ICA (0.60%: 2479.00),Estampilla Pro Cultura (2.00%: 8263.20),Iva Compras Gravadas (15.00%: 11775.00),Estampilla Pro-Hospital (1.00%: 4131.60),Tasa Pro Deporte y Recreación (2.00%: 8263.20),Estampilla pro-justicia familiar (2.00%: 8263.20)
CS-019-2026,CE N° 00218,30/04/2026,WCP INGENIERIA S.A.S,2.1.2.02.02.008,318587,27976.80,290610.20,Industria y comercio ICA (0.60%: 1606.30),Estampilla Pro Cultura (2.00%: 5354.40),Iva Compras Gravadas (15.00%: 7630.10),Estampilla Pro-Hospital (1.00%: 2677.20),Tasa Pro Deporte y Recreación (2.00%: 5354.40),Estampilla pro-justicia familiar (2.00%: 5354.40)
CS-019-2026,CE N° 00219,30/04/2026,WCP INGENIERIA S.A.S,2.1.2.02.02.008,1150777,125231.60,1025545.40,Industria y comercio ICA (0.60%: 5802.20),Estampilla Pro Cultura (2.00%: 19340.80),Iva Compras Gravadas (15.00%: 27560.60),Estampilla Pro-Hospital (1.00%: 9670.40),Retención Compras 2.5 (2.50%: 24176.00),Tasa Pro Deporte y Recreación (2.00%: 19340.80),Estampilla pro-justicia familiar (2.00%: 19340.80)
CS-019-2026,CE N° 00321,19/06/2026,WCP INGENIERIA S.A.S,2.1.2.02.02.008,775451,84387.20,691063.80,Industria y comercio ICA (0.60%: 3909.80),Estampilla Pro Cultura (2.00%: 13032.80),Iva Compras Gravadas (15.00%: 18571.60),Estampilla Pro-Hospital (1.00%: 6516.40),Retención Compras 2.5 (2.50%: 16291.00),Tasa Pro Deporte y Recreación (2.00%: 13032.80),Estampilla pro-justicia familiar (2.00%: 13032.80)
CS-019-2026,CE N° 00322,19/06/2026,WCP INGENIERIA S.A.S,2.1.2.02.02.008,553588,48613.40,504974.60,Industria y comercio ICA (0.60%: 2791.20),Estampilla Pro Cultura (2.00%: 9304.00),Iva Compras Gravadas (15.00%: 13258.20),Estampilla Pro-Hospital (1.00%: 4652.00),Tasa Pro Deporte y Recreación (2.00%: 9304.00),Estampilla pro-justicia familiar (2.00%: 9304.00)
CS-019-2026,CE N° 00370,07/07/2026,WCP INGENIERIA S.A.S,2.1.2.02.02.008,435540,38247,397293,Industria y comercio ICA (0.60%: 2196.00),Estampilla Pro Cultura (2.00%: 7320.00),Iva Compras Gravadas (15.00%: 10431.00),Estampilla Pro-Hospital (1.00%: 3660.00),Tasa Pro Deporte y Recreación (2.00%: 7320.00),Estampilla pro-justicia familiar (2.00%: 7320.00)
CPS-021-2026,CE N° 00096,25/02/2026,STRAPARTES DIESEL S.A.S.,2.1.2.02.02.008,1687000,178327.80,1508672.20,Industria y comercio ICA (0.60%: 9149.60),Estampilla Pro Cultura (2.00%: 30498.80),Iva Compras Gravadas (15.00%: 24308.90),Estampilla Pro-Hospital (1.00%: 15249.40),Retención Compras 2.5 (2.50%: 38123.50),Tasa Pro Deporte y Recreación (2.00%: 30498.80),Estampilla pro-justicia familiar (2.00%: 30498.80)
CPS-021-2026,CE N° 00097,25/02/2026,STRAPARTES DIESEL S.A.S.,2.1.2.02.02.008,1793000,190739.50,1602260.50,Industria y comercio ICA (0.60%: 9576.80),Estampilla Pro Cultura (2.00%: 31922.70),Iva Compras Gravadas (15.00%: 29529.90),Estampilla Pro-Hospital (1.00%: 15961.30),Retención Compras 2.5 (2.50%: 39903.40),Tasa Pro Deporte y Recreación (2.00%: 31922.70),Estampilla pro-justicia familiar (2.00%: 31922.70)
CPS-021-2026,CE N° 00174,30/03/2026,STRAPARTES DIESEL S.A.S.,2.1.2.02.02.008,190000,23071.50,166928.50,Industria y comercio ICA (0.60%: 958.00),Servicios personas jurídicas (4.00%: 6386.60),Estampilla Pro Cultura (2.00%: 3193.30),Iva por Servicios Gravados (15.00%: 4550.40),Estampilla Pro-Hospital (1.00%: 1596.60),Tasa Pro Deporte y Recreación (2.00%: 3193.30),Estampilla pro-justicia familiar (2.00%: 3193.30)
CPS-021-2026,CE N° 00224,04/05/2026,STRAPARTES DIESEL S.A.S.,2.1.2.02.02.008,5550000,595286.60,4954713.40,Industria y comercio ICA (0.60%: 29046.60),Estampilla Pro Cultura (2.00%: 96821.90),Iva Compras Gravadas (15.00%: 106336.10),Estampilla Pro-Hospital (1.00%: 48410.90),Retención Compras 2.5 (2.50%: 121027.30),Tasa Pro Deporte y Recreación (2.00%: 96821.90),Estampilla pro-justicia familiar (2.00%: 96821.90)
CPS-021-2026,CE N° 00225,04/05/2026,STRAPARTES DIESEL S.A.S.,2.1.2.02.02.008,3490000,378386,3111614,Industria y comercio ICA (0.60%: 17769.10),Estampilla Pro Cultura (2.00%: 59230.30),Iva Compras Gravadas (15.00%: 79273.10),Estampilla Pro-Hospital (1.00%: 29615.10),Retención Compras 2.5 (2.50%: 74037.80),Tasa Pro Deporte y Recreación (2.00%: 59230.30),Estampilla pro-justicia familiar (2.00%: 59230.30)
CPS-021-2026,CE N° 00226,04/05/2026,STRAPARTES DIESEL S.A.S.,2.1.2.02.02.008,150000,13172.30,136827.70,Industria y comercio ICA (0.60%: 756.30),Estampilla Pro Cultura (2.00%: 2521.00),Iva Compras Gravadas (15.00%: 3592.50),Estampilla Pro-Hospital (1.00%: 1260.50),Tasa Pro Deporte y Recreación (2.00%: 2521.00),Estampilla pro-justicia familiar (2.00%: 2521.00)
CPS-021-2026,CE N° 00273,26/05/2026,STRAPARTES DIESEL S.A.S.,2.1.2.02.02.008,7200000,783529.40,6416470.60,Industria y comercio ICA (0.60%: 36302.50),Estampilla Pro Cultura (2.00%: 121008.40),Iva Compras Gravadas (15.00%: 172437.00),Estampilla Pro-Hospital (1.00%: 60504.20),Retención Compras 2.5 (2.50%: 151260.50),Tasa Pro Deporte y Recreación (2.00%: 121008.40),Estampilla pro-justicia familiar (2.00%: 121008.40)
CPS-021-2026,CE N° 00328,19/06/2026,STRAPARTES DIESEL S.A.S.,2.1.2.02.02.008,6412000,697776.60,5714223.40,Industria y comercio ICA (0.60%: 32329.40),Estampilla Pro Cultura (2.00%: 107764.70),Iva Compras Gravadas (15.00%: 153564.80),Estampilla Pro-Hospital (1.00%: 53882.40),Retención Compras 2.5 (2.50%: 134705.90),Tasa Pro Deporte y Recreación (2.00%: 107764.70),Estampilla pro-justicia familiar (2.00%: 107764.70)
CPS-021-2026,CE N° 00329,19/06/2026,STRAPARTES DIESEL S.A.S.,2.1.2.02.02.008,290000,25466.50,264533.50,Industria y comercio ICA (0.60%: 1462.20),Estampilla Pro Cultura (2.00%: 4874.00),Iva Compras Gravadas (15.00%: 6945.30),Estampilla Pro-Hospital (1.00%: 2437.00),Tasa Pro Deporte y Recreación (2.00%: 4874.00),Estampilla pro-justicia familiar (2.00%: 4874.00)
CPS-021-2026,CE N° 00330,19/06/2026,STRAPARTES DIESEL S.A.S.,2.1.2.02.02.008,960000,104470.70,855529.30,Industria y comercio ICA (0.60%: 4840.30),Estampilla Pro Cultura (2.00%: 16134.50),Iva Compras Gravadas (15.00%: 22991.60),Estampilla Pro-Hospital (1.00%: 8067.20),Retención Compras 2.5 (2.50%: 20168.10),Tasa Pro Deporte y Recreación (2.00%: 16134.50),Estampilla pro-justicia familiar (2.00%: 16134.50)
CPS-021-2026,CE N° 00331,19/06/2026,STRAPARTES DIESEL S.A.S.,2.1.2.02.02.008,760000,57760,702240,Industria y comercio ICA (0.60%: 4560.00),Estampilla Pro Cultura (2.00%: 15200.00),Estampilla Pro-Hospital (1.00%: 7600.00),Tasa Pro Deporte y Recreación (2.00%: 15200.00),Estampilla pro-justicia familiar (2.00%: 15200.00)
CS-024-2026,CE N° 00128,04/03/2026,M360 COMPANY SAS,2.1.2.01.01.003.03.02,2688778,286401.40,2402376.60,Industria y comercio ICA (0.60%: 14316.20),Estampilla Pro Cultura (2.00%: 47720.50),Iva Compras Gravadas (15.00%: 45412.70),Estampilla Pro-Hospital (1.00%: 23860.30),Retención Compras 2.5 (2.50%: 59650.70),Tasa Pro Deporte y Recreación (2.00%: 47720.50),Estampilla pro-justicia familiar (2.00%: 47720.50)
CS-024-2026,CE N° 00129,04/03/2026,M360 COMPANY SAS,2.1.2.01.01.004.01.01.02,991440,107892.20,883547.80,Industria y comercio ICA (0.60%: 4998.90),Estampilla Pro Cultura (2.00%: 16662.90),Iva Compras Gravadas (15.00%: 23744.60),Estampilla Pro-Hospital (1.00%: 8331.40),Retención Compras 2.5 (2.50%: 20828.60),Tasa Pro Deporte y Recreación (2.00%: 16662.90),Estampilla pro-justicia familiar (2.00%: 16662.90)
CS-024-2026,CE N° 00130,04/03/2026,M360 COMPANY SAS,2.1.2.02.01.003,3489023,379687.70,3109335.30,Industria y comercio ICA (0.60%: 17591.70),Estampilla Pro Cultura (2.00%: 58639.00),Iva Compras Gravadas (15.00%: 83560.70),Estampilla Pro-Hospital (1.00%: 29319.50),Retención Compras 2.5 (2.50%: 73298.80),Tasa Pro Deporte y Recreación (2.00%: 58639.00),Estampilla pro-justicia familiar (2.00%: 58639.00)
CS-025-2026,CE N° 00112,03/03/2026,M360 COMPANY SAS,2.1.2.02.02.008,3260620,354832.10,2905787.90,Industria y comercio ICA (0.60%: 16440.10),Estampilla Pro Cultura (2.00%: 54800.30),Iva Compras Gravadas (15.00%: 78090.50),Estampilla Pro-Hospital (1.00%: 27400.20),Retención Compras 2.5 (2.50%: 68500.40),Tasa Pro Deporte y Recreación (2.00%: 54800.30),Estampilla pro-justicia familiar (2.00%: 54800.30)
CS-025-2026,CE N° 00113,03/03/2026,M360 COMPANY SAS,2.1.2.02.02.008,13125888,1422392.50,11703495.50,Industria y comercio ICA (0.60%: 66917.20),Estampilla Pro Cultura (2.00%: 223057.40),Iva Compras Gravadas (15.00%: 295952.60),Estampilla Pro-Hospital (1.00%: 111528.70),Retención Compras 2.5 (2.50%: 278821.80),Tasa Pro Deporte y Recreación (2.00%: 223057.40),Estampilla pro-justicia familiar (2.00%: 223057.40)
CS-025-2026,CE N° 00114,03/03/2026,M360 COMPANY SAS,2.1.2.02.01.003,6212506,674111.90,5538394.10,Industria y comercio ICA (0.60%: 31562.90),Estampilla Pro Cultura (2.00%: 105209.80),Iva Compras Gravadas (15.00%: 142802.40),Estampilla Pro-Hospital (1.00%: 52604.90),Retención Compras 2.5 (2.50%: 131512.30),Tasa Pro Deporte y Recreación (2.00%: 105209.80),Estampilla pro-justicia familiar (2.00%: 105209.80)
CS-027-2026,CE N° 00060,05/02/2026,ASOCIACION DE JUNTAS DE ACCION COMUNAL,2.1.2.02.02.008,7635500,351233,7284267,Industria y comercio ICA (0.60%: 45813.00),Tasa Pro Deporte y Recreación (2.00%: 152710.00),Estampilla pro-justicia familiar (2.00%: 152710.00)
CS-028-2026,CE N° 00103,27/02/2026,HORACIO DE JESUS DUQUE JARAMILLO,2.3.2.02.02.005,14587800,1567345.60,13020454.40,Industria y comercio ICA (0.60%: 76019.30),Estampilla Pro Cultura (2.00%: 253397.80),Iva Compras Gravadas (15.00%: 287686.80),Estampilla Pro-Hospital (1.00%: 126698.90),Retención Compras 2.5 (2.50%: 316747.20),Tasa Pro Deporte y Recreación (2.00%: 253397.80),Estampilla pro-justicia familiar (2.00%: 253397.80)
CS-028-2026,CE N° 00216,30/04/2026,HORACIO DE JESUS DUQUE JARAMILLO,2.3.2.02.02.005,9786000,1056428.80,8729571.20,Industria y comercio ICA (0.60%: 50384.20),Estampilla Pro Cultura (2.00%: 167947.50),Iva Compras Gravadas (15.00%: 208294.10),Estampilla Pro-Hospital (1.00%: 83973.70),Retención Compras 2.5 (2.50%: 209934.30),Tasa Pro Deporte y Recreación (2.00%: 167947.50),Estampilla pro-justicia familiar (2.00%: 167947.50)
CS-028-2026,CE N° 00265,21/05/2026,HORACIO DE JESUS DUQUE JARAMILLO,2.3.2.02.02.005,6180000,661480.20,5518519.80,Industria y comercio ICA (0.60%: 32512.60),Estampilla Pro Cultura (2.00%: 108375.50),Iva Compras Gravadas (15.00%: 114184.10),Estampilla Pro-Hospital (1.00%: 54187.70),Retención Compras 2.5 (2.50%: 135469.30),Tasa Pro Deporte y Recreación (2.00%: 108375.50),Estampilla pro-justicia familiar (2.00%: 108375.50)
CS-028-2026,CE N° 00348,01/07/2026,HORACIO DE JESUS DUQUE JARAMILLO,2.3.2.02.02.005,2945000,319624.80,2625375.20,Industria y comercio ICA (0.60%: 14954.10),Estampilla Pro Cultura (2.00%: 49847.10),Iva Compras Gravadas (15.00%: 67897.10),Estampilla Pro-Hospital (1.00%: 24923.50),Retención Compras 2.5 (2.50%: 62308.80),Tasa Pro Deporte y Recreación (2.00%: 49847.10),Estampilla pro-justicia familiar (2.00%: 49847.10)
CS-028-2026,CE N° 00403,04/08/2026,HORACIO DE JESUS DUQUE JARAMILLO,2.3.2.02.02.005,2284500,245808.90,2038691.10,Industria y comercio ICA (0.60%: 11861.20),Estampilla Pro Cultura (2.00%: 39537.20),Iva Compras Gravadas (15.00%: 46146.00),Estampilla Pro-Hospital (1.00%: 19768.60),Retención Compras 2.5 (2.50%: 49421.50),Tasa Pro Deporte y Recreación (2.00%: 39537.20),Estampilla pro-justicia familiar (2.00%: 39537.20)
CS-030-2026,CE N° 00055,04/02/2026,ASOCIACION DE JUNTAS DE ACCION COMUNAL,2.3.2.02.02.005,22825550,1049975.30,21775574.70,Industria y comercio ICA (0.60%: 136953.30),Tasa Pro Deporte y Recreación (2.00%: 456511.00),Estampilla pro-justicia familiar (2.00%: 456511.00)
CS-030-2026,CE N° 00078,10/02/2026,ASOCIACION DE JUNTAS DE ACCION COMUNAL,2.1.2.02.02.006,2867400,131900.40,2735499.60,Industria y comercio ICA (0.60%: 17204.40),Estampilla Pro Cultura (2.00%: 57348.00),Estampilla pro-justicia familiar (2.00%: 57348.00)
CS-030-2026,CE N° 00082,13/02/2026,ASOCIACION DE JUNTAS DE ACCION COMUNAL,2.1.2.02.02.006,32000000,1472000,30528000,Industria y comercio ICA (0.60%: 192000.00),Tasa Pro Deporte y Recreación (2.00%: 640000.00),Estampilla pro-justicia familiar (2.00%: 640000.00)
CS-030-2026,CE N° 00087,23/02/2026,ASOCIACION DE JUNTAS DE ACCION COMUNAL,2.1.2.02.01.003,7260000,333960,6926040,Industria y comercio ICA (0.60%: 43560.00),Tasa Pro Deporte y Recreación (2.00%: 145200.00),Estampilla pro-justicia familiar (2.00%: 145200.00)
CS-037-2026,CE N° 00104,27/02/2026,AGUAFER SAS,2.3.2.02.02.005,7990017,869501.90,7120515.10,Industria y comercio ICA (0.60%: 40285.80),Estampilla Pro Cultura (2.00%: 134286.00),Iva Compras Gravadas (15.00%: 191357.60),Estampilla Pro-Hospital (1.00%: 67143.00),Retención Compras 2.5 (2.50%: 167857.50),Tasa Pro Deporte y Recreación (2.00%: 134286.00),Estampilla pro-justicia familiar (2.00%: 134286.00)
CPS-001-2026,CE N° 00032,29/01/2026,SEBASTIAN MONTOYA OCHOA,2.1.2.02.02.008,4500000,252000,4248000,Industria y comercio ICA (0.60%: 27000.00),Estampilla Pro Cultura (2.00%: 90000.00),Estampilla Pro-Hospital (1.00%: 45000.00),Tasa Pro Deporte y Recreación (2.00%: 90000.00)
CPS-001-2026,CE N° 00105,27/02/2026,SEBASTIAN MONTOYA OCHOA,2.1.2.02.02.008,4500000,252000,4248000,Industria y comercio ICA (0.60%: 27000.00),Estampilla Pro Cultura (2.00%: 90000.00),Estampilla Pro-Hospital (1.00%: 45000.00),Tasa Pro Deporte y Recreación (2.00%: 90000.00)
CPS-001-2026,CE N° 00166,27/03/2026,SEBASTIAN MONTOYA OCHOA,2.1.2.02.02.008,4500000,252000,4248000,Industria y comercio ICA (0.60%: 27000.00),Estampilla Pro Cultura (2.00%: 90000.00),Estampilla Pro-Hospital (1.00%: 45000.00),Tasa Pro Deporte y Recreación (2.00%: 90000.00)
CPS-002-2026,CE N° 00086,17/02/2026,LUIS HERNANDO SALAZAR SALAZAR,2.1.2.02.02.008,2140000,119840,2020160,Industria y comercio ICA (0.60%: 12840.00),Estampilla Pro Cultura (2.00%: 42800.00),Estampilla Pro-Hospital (1.00%: 21400.00),Tasa Pro Deporte y Recreación (2.00%: 42800.00)
CPS-002-2026,CE N° 00152,17/03/2026,LUIS HERNANDO SALAZAR SALAZAR,2.1.2.02.02.008,2140000,119840,2020160,Industria y comercio ICA (0.60%: 12840.00),Estampilla Pro Cultura (2.00%: 42800.00),Estampilla Pro-Hospital (1.00%: 21400.00),Tasa Pro Deporte y Recreación (2.00%: 42800.00)
CPS-003-2026,CE N° 00061,05/02/2026,JUAN DAVID VARGAS ESCOBAR,2.1.2.02.02.008,3300000,184800,3115200,Industria y comercio ICA (0.60%: 19800.00),Estampilla Pro Cultura (2.00%: 66000.00),Estampilla Pro-Hospital (1.00%: 33000.00),Tasa Pro Deporte y Recreación (2.00%: 66000.00)
CPS-003-2026,CE N° 00132,04/03/2026,JUAN DAVID VARGAS ESCOBAR,2.1.2.02.02.008,3300000,184800,3115200,Industria y comercio ICA (0.60%: 19800.00),Estampilla Pro Cultura (2.00%: 66000.00),Estampilla Pro-Hospital (1.00%: 33000.00),Tasa Pro Deporte y Recreación (2.00%: 66000.00)
CPS-003-2026,CE N° 00173,30/03/2026,JUAN DAVID VARGAS ESCOBAR,2.1.2.02.02.008,3300000,184800,3115200,Industria y comercio ICA (0.60%: 19800.00),Estampilla Pro Cultura (2.00%: 66000.00),Estampilla Pro-Hospital (1.00%: 33000.00),Tasa Pro Deporte y Recreación (2.00%: 66000.00)
CPS-004-2026,CE N° 00276,28/05/2026,ASESORIAS Y SOLUCIONES EXITOSAS S.A.S.,2.1.2.02.02.008,5617500,918154.50,4699345.50,Industria y comercio ICA (0.60%: 28323.50),Estampilla Pro Cultura (2.00%: 94411.80),Iva por Servicios Gravados (15.00%: 134536.80),Personas Jurídicas (11.00%: 519264.70),Estampilla Pro-Hospital (1.00%: 47205.90),Tasa Pro Deporte y Recreación (2.00%: 94411.80)
CPS-004-2026,CE N° 00277,28/05/2026,ASESORIAS Y SOLUCIONES EXITOSAS S.A.S.,2.1.2.02.02.008,5617500,918154.50,4699345.50,Industria y comercio ICA (0.60%: 28323.50),Estampilla Pro Cultura (2.00%: 94411.80),Iva por Servicios Gravados (15.00%: 134536.80),Personas Jurídicas (11.00%: 519264.70),Estampilla Pro-Hospital (1.00%: 47205.90),Tasa Pro Deporte y Recreación (2.00%: 94411.80)
CPS-004-2026,CE N° 00278,28/05/2026,ASESORIAS Y SOLUCIONES EXITOSAS S.A.S.,2.1.2.02.02.008,5617500,918154.50,4699345.50,Industria y comercio ICA (0.60%: 28323.50),Estampilla Pro Cultura (2.00%: 94411.80),Iva por Servicios Gravados (15.00%: 134536.80),Personas Jurídicas (11.00%: 519264.70),Estampilla Pro-Hospital (1.00%: 47205.90),Tasa Pro Deporte y Recreación (2.00%: 94411.80)
CPS-004-2026,CE N° 00279,28/05/2026,ASESORIAS Y SOLUCIONES EXITOSAS S.A.S.,2.1.2.02.02.008,5617500,918154.50,4699345.50,Industria y comercio ICA (0.60%: 28323.50),Estampilla Pro Cultura (2.00%: 94411.80),Iva por Servicios Gravados (15.00%: 134536.80),Personas Jurídicas (11.00%: 519264.70),Estampilla Pro-Hospital (1.00%: 47205.90),Tasa Pro Deporte y Recreación (2.00%: 94411.80)
CPS-004-2026,CE N° 00339,23/06/2026,ASESORIAS Y SOLUCIONES EXITOSAS S.A.S.,2.1.2.02.02.008,5617500,918154.50,4699345.50,Industria y comercio ICA (0.60%: 28323.50),Estampilla Pro Cultura (2.00%: 94411.80),Iva por Servicios Gravados (15.00%: 134536.80),Personas Jurídicas (11.00%: 519264.70),Estampilla Pro-Hospital (1.00%: 47205.90),Tasa Pro Deporte y Recreación (2.00%: 94411.80)
CPS-004-2026,CE N° 00376,08/07/2026,ASESORIAS Y SOLUCIONES EXITOSAS S.A.S.,2.1.2.02.02.008,5617500,918154.50,4699345.50,Industria y comercio ICA (0.60%: 28323.50),Estampilla Pro Cultura (2.00%: 94411.80),Iva por Servicios Gravados (15.00%: 134536.80),Personas Jurídicas (11.00%: 519264.70),Estampilla Pro-Hospital (1.00%: 47205.90),Tasa Pro Deporte y Recreación (2.00%: 94411.80)
CPS-005-2026,CE N° 00059,05/02/2026,JUAN DAVID VARGAS ESCOBAR,2.1.2.02.02.008,2200000,123200,2076800,Industria y comercio ICA (0.60%: 13200.00),Estampilla Pro Cultura (2.00%: 44000.00),Estampilla Pro-Hospital (1.00%: 22000.00),Tasa Pro Deporte y Recreación (2.00%: 44000.00)
CPS-005-2026,CE N° 00131,04/03/2026,JUAN DAVID VARGAS ESCOBAR,2.1.2.02.02.008,2200000,123200,2076800,Industria y comercio ICA (0.60%: 13200.00),Estampilla Pro Cultura (2.00%: 44000.00),Estampilla Pro-Hospital (1.00%: 22000.00),Tasa Pro Deporte y Recreación (2.00%: 44000.00)
CPS-005-2026,CE N° 00169,30/03/2026,JUAN DAVID VARGAS ESCOBAR,2.1.2.02.02.008,2200000,123200,2076800,Industria y comercio ICA (0.60%: 13200.00),Estampilla Pro Cultura (2.00%: 44000.00),Estampilla Pro-Hospital (1.00%: 22000.00),Tasa Pro Deporte y Recreación (2.00%: 44000.00)
CPS-006-2026,CE N° 00093,25/02/2026,SISTEMAS ARIES S.A.S.,2.1.2.02.02.008,13365512,1566797.50,11798714.50,Industria y comercio ICA (0.60%: 67389.10),Estampilla Pro Cultura (2.00%: 224630.50),Iva Compras Gravadas (15.00%: 320098.40),Estampilla Pro-Hospital (1.00%: 112315.20),Compras Software y Licencias (3.50%: 393103.30),Tasa Pro Deporte y Recreación (2.00%: 224630.50),Estampilla pro-justicia familiar (2.00%: 224630.50)
CPS-007-2026,CE N° 00037,30/01/2026,YAKELINE CASAS GOMEZ,2.1.2.02.02.008,4500000,252000,4248000,Industria y comercio ICA (0.60%: 27000.00),Estampilla Pro Cultura (2.00%: 90000.00),Estampilla Pro-Hospital (1.00%: 45000.00),Tasa Pro Deporte y Recreación (2.00%: 90000.00)
CPS-007-2026,CE N° 00110,02/03/2026,YAKELINE CASAS GOMEZ,2.1.2.02.02.008,4500000,252000,4248000,Industria y comercio ICA (0.60%: 27000.00),Estampilla Pro Cultura (2.00%: 90000.00),Estampilla Pro-Hospital (1.00%: 45000.00),Tasa Pro Deporte y Recreación (2.00%: 90000.00)
CPS-007-2026,CE N° 00167,27/03/2026,YAKELINE CASAS GOMEZ,2.1.2.02.02.008,4500000,252000,4248000,Industria y comercio ICA (0.60%: 27000.00),Estampilla Pro Cultura (2.00%: 90000.00),Estampilla Pro-Hospital (1.00%: 45000.00),Tasa Pro Deporte y Recreación (2.00%: 90000.00)
CPS-010-2026,CE N° 00075,10/02/2026,ANALTEC LABORATORIOS SAS,2.1.2.02.02.008,1044432,121557.90,922874.10,Servicios personas juridicas (4.00%: 35107.00),Estampilla Pro Cultura (2.00%: 17553.50),Iva por Servicios Gravados (15.00%: 25013.70),Estampilla Pro-Hospital (1.00%: 8776.70),Tasa Pro Deporte y Recreación (2.00%: 17553.50),Estampilla pro-justicia familiar (2.00%: 17553.50)
CPS-010-2026,CE N° 00149,12/03/2026,ANALTEC LABORATORIOS SAS,2.1.2.02.02.008,1044432,121557.90,922874.10,Servicios personas juridicas (4.00%: 35107.00),Estampilla Pro Cultura (2.00%: 17553.50),Iva por Servicios Gravados (15.00%: 25013.70),Estampilla Pro-Hospital (1.00%: 8776.70),Tasa Pro Deporte y Recreación (2.00%: 17553.50),Estampilla pro-justicia familiar (2.00%: 17553.50)
CPS-016-2026,CE N° 00153,17/03/2026,CONSULTORIA INTEGRAL EN SERVICIOS PUBLICOS Y AMBIENTALES CISPA S.A.S,2.1.2.02.02.008,5103000,362356,4740644,Industria y comercio ICA (0.60%: 25729.40),Estampilla Pro Cultura (2.00%: 85764.70),Iva por Servicios Gravados (15.00%: 122214.80),Estampilla Pro-Hospital (1.00%: 42882.40),Tasa Pro Deporte y Recreación (2.00%: 85764.70)
CPS-020-2026,CE N° 00148,12/03/2026,JOSE ALBERTO TOBON MAZO,2.1.2.02.02.008,1880000,142880,1737120,Industria y comercio ICA (0.60%: 11280.00),Estampilla Pro Cultura (2.00%: 37600.00),Estampilla Pro-Hospital (1.00%: 18800.00),Tasa Pro Deporte y Recreación (2.00%: 37600.00),Estampilla pro-justicia familiar (2.00%: 37600.00)
CPS-020-2026,CE N° 00257,15/05/2026,JOSE ALBERTO TOBON MAZO,2.1.2.02.02.008,1570000,119320,1450680,Industria y comercio ICA (0.60%: 9420.00),Estampilla Pro Cultura (2.00%: 31400.00),Estampilla Pro-Hospital (1.00%: 15700.00),Tasa Pro Deporte y Recreación (2.00%: 31400.00),Estampilla pro-justicia familiar (2.00%: 31400.00)
CPS-020-2026,CE N° 00368,07/07/2026,JOSE ALBERTO TOBON MAZO,2.1.2.02.02.008,1620000,123120,1496880,Industria y comercio ICA (0.60%: 9720.00),Estampilla Pro Cultura (2.00%: 32400.00),Estampilla Pro-Hospital (1.00%: 16200.00),Tasa Pro Deporte y Recreación (2.00%: 32400.00),Estampilla pro-justicia familiar (2.00%: 32400.00)
CPS-008-2026,CE N° 00072,09/02/2026,JOSE ROMUALDO MOLINA TOBON,2.1.2.02.02.008,3564000,199584,3364416,Industria y comercio ICA (0.60%: 21384.00),Estampilla Pro Cultura (2.00%: 71280.00),Estampilla Pro-Hospital (1.00%: 35640.00),Tasa Pro Deporte y Recreación (2.00%: 71280.00)
CPS-008-2026,CE N° 00160,19/03/2026,JOSE ROMUALDO MOLINA TOBON,2.1.2.02.02.008,3564000,199584,3364416,Industria y comercio ICA (0.60%: 21384.00),Estampilla Pro Cultura (2.00%: 71280.00),Estampilla Pro-Hospital (1.00%: 35640.00),Tasa Pro Deporte y Recreación (2.00%: 71280.00)
CPS-008-2026,CE N° 00193,13/04/2026,JOSE ROMUALDO MOLINA TOBON,2.1.2.02.02.008,3564000,199584,3364416,Industria y comercio ICA (0.60%: 21384.00),Estampilla Pro Cultura (2.00%: 71280.00),Estampilla Pro-Hospital (1.00%: 35640.00),Tasa Pro Deporte y Recreación (2.00%: 71280.00)
CPS-008-2026,CE N° 00215,30/04/2026,JOSE ROMUALDO MOLINA TOBON,2.1.2.02.02.008,3564000,199584,3364416,Industria y comercio ICA (0.60%: 21384.00),Estampilla Pro Cultura (2.00%: 71280.00),Estampilla Pro-Hospital (1.00%: 35640.00),Tasa Pro Deporte y Recreación (2.00%: 71280.00)
CPS-008-2026,CE N° 00300,03/06/2026,JOSE ROMUALDO MOLINA TOBON,2.1.2.02.02.008,3564000,199584,3364416,Industria y comercio ICA (0.60%: 21384.00),Estampilla Pro Cultura (2.00%: 71280.00),Estampilla Pro-Hospital (1.00%: 35640.00),Tasa Pro Deporte y Recreación (2.00%: 71280.00)
CPS-008-2026,CE N° 00346,01/07/2026,JOSE ROMUALDO MOLINA TOBON,2.1.2.02.02.008,3564000,199584,3364416,Industria y comercio ICA (0.60%: 21384.00),Estampilla Pro Cultura (2.00%: 71280.00),Estampilla Pro-Hospital (1.00%: 35640.00),Tasa Pro Deporte y Recreación (2.00%: 71280.00)
CPS-008-2026,CE N° 00394,31/07/2026,JOSE ROMUALDO MOLINA TOBON,2.1.2.02.02.008,3564000,199584,3364416,Industria y comercio ICA (0.60%: 21384.00),Estampilla Pro Cultura (2.00%: 71280.00),Estampilla Pro-Hospital (1.00%: 35640.00),Tasa Pro Deporte y Recreación (2.00%: 71280.00)
CPS-009-2026,CE N° 00036,30/01/2026,MANUELA GALLEGO ESCOBAR,2.3.2.02.02.009,4000000,224000,3776000,Industria y comercio ICA (0.60%: 24000.00),Estampilla Pro Cultura (2.00%: 80000.00),Estampilla Pro-Hospital (1.00%: 40000.00),Tasa Pro Deporte y Recreación (2.00%: 80000.00)
CPS-009-2026,CE N° 00106,27/02/2026,MANUELA GALLEGO ESCOBAR,2.3.2.02.02.009,4000000,224000,3776000,Industria y comercio ICA (0.60%: 24000.00),Estampilla Pro Cultura (2.00%: 80000.00),Estampilla Pro-Hospital (1.00%: 40000.00),Tasa Pro Deporte y Recreación (2.00%: 80000.00)
CPS-009-2026,CE N° 00165,27/03/2026,MANUELA GALLEGO ESCOBAR,2.3.2.02.02.009,4000000,224000,3776000,Industria y comercio ICA (0.60%: 24000.00),Estampilla Pro Cultura (2.00%: 80000.00),Estampilla Pro-Hospital (1.00%: 40000.00),Tasa Pro Deporte y Recreación (2.00%: 80000.00)
CPS-009-2026,CE N° 00212,30/04/2026,MANUELA GALLEGO ESCOBAR,2.3.2.02.02.009,4000000,224000,3776000,Industria y comercio ICA (0.60%: 24000.00),Estampilla Pro Cultura (2.00%: 80000.00),Estampilla Pro-Hospital (1.00%: 40000.00),Tasa Pro Deporte y Recreación (2.00%: 80000.00)
CPS-009-2026,CE N° 00305,09/06/2026,MANUELA GALLEGO ESCOBAR,2.3.2.02.02.009,4000000,224000,3776000,Industria y comercio ICA (0.60%: 24000.00),Estampilla Pro Cultura (2.00%: 80000.00),Estampilla Pro-Hospital (1.00%: 40000.00),Tasa Pro Deporte y Recreación (2.00%: 80000.00)
CPS-009-2026,CE N° 00373,08/07/2026,MANUELA GALLEGO ESCOBAR,2.3.2.02.02.009,4000000,224000,3776000,Industria y comercio ICA (0.60%: 24000.00),Estampilla Pro Cultura (2.00%: 80000.00),Estampilla Pro-Hospital (1.00%: 40000.00),Tasa Pro Deporte y Recreación (2.00%: 80000.00)
CPS-009-2026,CE N° 00389,30/07/2026,MANUELA GALLEGO ESCOBAR,2.3.2.02.02.009,4000000,224000,3776000,Industria y comercio ICA (0.60%: 24000.00),Estampilla Pro Cultura (2.00%: 80000.00),Estampilla Pro-Hospital (1.00%: 40000.00),Tasa Pro Deporte y Recreación (2.00%: 80000.00)
CPS-022-2026,CE N° 00172,30/03/2026,ESMERALDA RUBITH VALDERRAMA GIRALDO,2.3.2.02.02.009,6000000,336000,5664000,Industria y comercio ICA (0.60%: 36000.00),Estampilla Pro Cultura (2.00%: 120000.00),Estampilla Pro-Hospital (1.00%: 60000.00),Tasa Pro Deporte y Recreación (2.00%: 120000.00)
CPS-026-2026,CE N° 00109,02/03/2026,DANIEL ESTEBAN VILLA ARRUBLA,2.1.2.02.02.008,3200000,179200,3020800,Industria y comercio ICA (0.60%: 19200.00),Estampilla Pro Cultura (2.00%: 64000.00),Estampilla Pro-Hospital (1.00%: 32000.00),Tasa Pro Deporte y Recreación (2.00%: 64000.00)
CPS-026-2026,CE N° 00170,30/03/2026,DANIEL ESTEBAN VILLA ARRUBLA,2.1.2.02.02.008,3200000,179200,3020800,Industria y comercio ICA (0.60%: 19200.00),Estampilla Pro Cultura (2.00%: 64000.00),Estampilla Pro-Hospital (1.00%: 32000.00),Tasa Pro Deporte y Recreación (2.00%: 64000.00)
CPS-026-2026,CE N° 00213,30/04/2026,DANIEL ESTEBAN VILLA ARRUBLA,2.1.2.02.02.008,3200000,179200,3020800,Industria y comercio ICA (0.60%: 19200.00),Estampilla Pro Cultura (2.00%: 64000.00),Estampilla Pro-Hospital (1.00%: 32000.00),Tasa Pro Deporte y Recreación (2.00%: 64000.00)
CPS-026-2026,CE N° 00308,09/06/2026,DANIEL ESTEBAN VILLA ARRUBLA,2.1.2.02.02.008,3200000,179200,3020800,Industria y comercio ICA (0.60%: 19200.00),Estampilla Pro Cultura (2.00%: 64000.00),Estampilla Pro-Hospital (1.00%: 32000.00),Tasa Pro Deporte y Recreación (2.00%: 64000.00)
CPS-035-2026,CE N° 00077,10/02/2026,ASOCIACION DE JUNTAS DE ACCION COMUNAL,2.3.2.02.02.005,5961363,274222.80,5687140.20,Industria y comercio ICA (0.60%: 35768.20),Estampilla Pro Cultura (2.00%: 119227.30),Estampilla pro-justicia familiar (2.00%: 119227.30)
CPS-045-2026,CE N° 00421,19/08/2026,WILSON ALBERTO MUÑOZ ZAPATA,2.3.2.02.02.007,17083000,1981628,15101372,Industria y comercio ICA (0.60%: 102498.00),Estampilla Pro Cultura (2.00%: 341660.00),Estampilla Pro-Hospital (1.00%: 170830.00),Retención Arriendo de Bienes diferentes a Inmuebles (4.00%: 683320.00),Tasa Pro Deporte y Recreación (2.00%: 341660.00),Estampilla pro-justicia familiar (2.00%: 341660.00)
CS-011-2026,CE N° 00063,05/02/2026,M&E ESTACIONES S.A.S,2.1.2.02.01.003,4471148,319665.00,4151483.00,Industria y comercio ICA (0.60%: 24909.00), Estampilla Pro Cultura (2.00%: 83030.00), Estampilla Pro-Hospital (1.00%: 41515.00), Combustible (0.10%: 4151.00), Tasa Pro Deporte y Recreación (2.00%: 83030.00), Estampilla pro-juaticia familiar (2.00%: 83030.00)
CS-011-2026,CE N° 00094,25/02/2026,M&E ESTACIONES S.A.S,2.1.2.02.01.003,3185081,227716.00,2957365.00,Industria y comercio ICA (0.60%: 17744.00), Estampilla Pro Cultura (2.00%: 59147.00), Estampilla Pro-Hospital (1.00%: 29574.00), Combustible (0.10%: 2957.00), Tasa Pro Deporte y Recreación (2.00%: 59147.00), Estampilla pro-juaticia familiar (2.00%: 59147.00)
CS-011-2026,CE N° 00137,05/03/2026,M&E ESTACIONES S.A.S,2.1.2.02.01.003,3157843,225768.00,2932075.00,Industria y comercio ICA (0.60%: 17592.00), Estampilla Pro Cultura (2.00%: 58641.00), Estampilla Pro-Hospital (1.00%: 29321.00), Combustible (0.10%: 2932.00), Tasa Pro Deporte y Recreación (2.00%: 58641.00), Estampilla pro-juaticia familiar (2.00%: 58641.00)
CS-011-2026,CE N° 00161,19/03/2026,M&E ESTACIONES S.A.S,2.1.2.02.01.003,2991820,213898.00,2777922.00,Industria y comercio ICA (0.60%: 16667.00), Estampilla Pro Cultura (2.00%: 55558.00), Estampilla Pro-Hospital (1.00%: 27779.00), Combustible (0.10%: 2778.00), Tasa Pro Deporte y Recreación (2.00%: 55558.00), Estampilla pro-juaticia familiar (2.00%: 55558.00)
CS-011-2026,CE N° 00194,13/04/2026,M&E ESTACIONES S.A.S,2.1.2.02.01.003,3928838,280892.00,3647946.00,Industria y comercio ICA (0.60%: 21888.00), Estampilla Pro Cultura (2.00%: 72959.00), Estampilla Pro-Hospital (1.00%: 36479.00), Combustible (0.10%: 3648.00), Tasa Pro Deporte y Recreación (2.00%: 72959.00), Estampilla pro-juaticia familiar (2.00%: 72959.00)
CS-011-2026,CE N° 00204,22/04/2026,M&E ESTACIONES S.A.S,2.1.2.02.01.003,3623364,259051.00,3364313.00,Industria y comercio ICA (0.60%: 20186.00), Estampilla Pro Cultura (2.00%: 67286.00), Estampilla Pro-Hospital (1.00%: 33643.00), Combustible (0.10%: 3364.00), Tasa Pro Deporte y Recreación (2.00%: 67286.00), Estampilla pro-juaticia familiar (2.00%: 67286.00)
CS-011-2026,CE N° 00247,08/05/2026,M&E ESTACIONES S.A.S,2.1.2.02.01.003,2847829,203599.00,2644230.00,Industria y comercio ICA (0.60%: 15865.00), Estampilla Pro Cultura (2.00%: 52883.00), Estampilla Pro-Hospital (1.00%: 26441.00), Combustible (0.10%: 2644.00), Tasa Pro Deporte y Recreación (2.00%: 52883.00), Estampilla pro-juaticia familiar (2.00%: 52883.00)
CS-011-2026,CE N° 00266,21/05/2026,M&E ESTACIONES S.A.S,2.1.2.02.01.003,3283826,234776.00,3049050.00,Industria y comercio ICA (0.60%: 18294.00), Estampilla Pro Cultura (2.00%: 60981.00), Estampilla Pro-Hospital (1.00%: 30490.00), Combustible (0.10%: 3049.00), Tasa Pro Deporte y Recreación (2.00%: 60981.00), Estampilla pro-juaticia familiar (2.00%: 60981.00)
CS-011-2026,CE N° 00299,03/06/2026,M&E ESTACIONES S.A.S,2.1.2.02.01.003,2796995,199969.00,2597026.00,Industria y comercio ICA (0.60%: 15582.00), Estampilla Pro Cultura (2.00%: 51940.00), Estampilla Pro-Hospital (1.00%: 25970.00), Combustible (0.10%: 2597.00), Tasa Pro Deporte y Recreación (2.00%: 51940.00), Estampilla pro-juaticia familiar (2.00%: 51940.00)
CS-011-2026,CE N° 00327,19/06/2026,M&E ESTACIONES S.A.S,2.1.2.02.01.003,2942354,210357.00,2731997.00,Industria y comercio ICA (0.60%: 16392.00), Estampilla Pro Cultura (2.00%: 54638.00), Estampilla Pro-Hospital (1.00%: 27319.00), Combustible (0.10%: 2732.00), Tasa Pro Deporte y Recreación (2.00%: 54638.00), Estampilla pro-juaticia familiar (2.00%: 54638.00)
CS-011-2026,CE N° 00375,08/07/2026,M&E ESTACIONES S.A.S,2.1.2.02.01.003,3880548,277434.00,3603114.00,Industria y comercio ICA (0.60%: 21618.00), Estampilla Pro Cultura (2.00%: 72061.00), Estampilla Pro-Hospital (1.00%: 36030.00), Combustible (0.10%: 3603.00), Tasa Pro Deporte y Recreación (2.00%: 72061.00), Estampilla pro-juaticia familiar (2.00%: 72061.00)
CS-011-2026,CE N° 00386,27/07/2026,M&E ESTACIONES S.A.S,2.1.2.02.01.003,2995646,214171.00,2781475.00,Industria y comercio ICA (0.60%: 16689.00), Estampilla Pro Cultura (2.00%: 55629.00), Estampilla Pro-Hospital (1.00%: 27814.00), Combustible (0.10%: 2781.00), Tasa Pro Deporte y Recreación (2.00%: 55629.00), Estampilla pro-juaticia familiar (2.00%: 55629.00)
CS-012-2026,CE N° 00056,05/02/2026,ACUAMBIENTE S.A.S,2.3.2.02.01.003,574639,50462.00,524177.00,Industria y comercio ICA (0.60%: 2897.30), Estampilla Pro Cultura (2.00%: 9657.80), Iva Compras Gravadas (15.00%: 13762.40), Estampilla Pro-Hospital (1.00%: 4828.90), Tasa Pro Deporte y Recreación (2.00%: 9657.80), Estampilla pro-justicia-familiar (2.00%: 9657.80)
CS-012-2026,CE N° 00073,09/02/2026,ACUAMBIENTE S.A.S,2.3.2.02.01.003,859180,75449.00,783731.00,Industria y comercio ICA (0.60%: 4332.00), Estampilla Pro Cultura (2.00%: 14440.00), Iva Compras Gravadas (15.00%: 20577.00), Estampilla Pro-Hospital (1.00%: 7220.00), Tasa Pro Deporte y Recreación (2.00%: 14440.00), Estampilla pro-juaticia familiar (2.00%: 14440.00)
CS-012-2026,CE N° 00135,05/03/2026,ACUAMBIENTE S.A.S,2.3.2.02.01.003,8347126,908363.60,7438762.40,Industria y comercio ICA (0.60%: 42086.40), Estampilla Pro Cultura (2.00%: 140287.80), Iva Compras Gravadas (15.00%: 199910.10), Estampilla Pro-Hospital (1.00%: 70143.90), Retención Compras 2.5 (2.50%: 175359.80), Tasa Pro Deporte y Recreación (2.00%: 140287.80), Estampilla pro-juaticia familiar (2.00%: 140287.80)
CS-012-2026,CE N° 00136,05/03/2026,ACUAMBIENTE S.A.S,2.3.2.02.01.003,74970,6583.50,68386.50,Industria y comercio ICA (0.60%: 378.00), Estampilla Pro Cultura (2.00%: 1260.00), Iva Compras Gravadas (15.00%: 1795.50), Estampilla Pro-Hospital (1.00%: 630.00), Tasa Pro Deporte y Recreación (2.00%: 1260.00), Estampilla pro-juaticia familiar (2.00%: 1260.00)
CS-012-2026,CE N° 00223,04/05/2026,ACUAMBIENTE S.A.S,2.3.2.02.01.003,7466231,812501.70,6653729.30,Industria y comercio ICA (0.60%: 37644.90), Estampilla Pro Cultura (2.00%: 125482.90), Iva Compras Gravadas (15.00%: 178813.10), Estampilla Pro-Hospital (1.00%: 62741.40), Retención Compras 2.5 (2.50%: 156853.60), Tasa Pro Deporte y Recreación (2.00%: 125482.90), Estampilla pro-juaticia familiar (2.00%: 125482.90)
CS-012-2026,CE N° 00244,08/05/2026,ACUAMBIENTE S.A.S,2.3.2.02.01.003,640220,69671.00,570549.00,Industria y comercio ICA (0.60%: 3228.00), Estampilla Pro Cultura (2.00%: 10760.00), Iva Compras Gravadas (15.00%: 15333.00), Estampilla Pro-Hospital (1.00%: 5380.00), Retención Compras 2.5 (2.50%: 13450.00), Tasa Pro Deporte y Recreación (2.00%: 10760.00), Estampilla pro-juaticia familiar (2.00%: 10760.00)
CS-012-2026,CE N° 00267,22/05/2026,ACUAMBIENTE S.A.S,2.3.2.02.01.003,940000,71440.00,868560.00,Industria y comercio ICA (0.60%: 5640.00), Estampilla Pro Cultura (2.00%: 18800.00), Estampilla Pro-Hospital (1.00%: 9400.00), Tasa Pro Deporte y Recreación (2.00%: 18800.00), Estampilla pro-juaticia familiar (2.00%: 18800.00)
CS-012-2026,CE N° 00268,22/05/2026,ACUAMBIENTE S.A.S,2.3.2.02.01.003,1509991,164322.60,1345668.40,Industria y comercio ICA (0.60%: 7613.40), Estampilla Pro Cultura (2.00%: 25378.00), Iva Compras Gravadas (15.00%: 36163.70), Estampilla Pro-Hospital (1.00%: 12689.00), Retención Compras 2.5 (2.50%: 31722.50), Tasa Pro Deporte y Recreación (2.00%: 25378.00), Estampilla pro-juaticia familiar (2.00%: 25378.00)
CS-012-2026,CE N° 00269,22/05/2026,ACUAMBIENTE S.A.S,2.3.2.02.01.003,557229,48933.20,508295.80,Industria y comercio ICA (0.60%: 2809.60), Estampilla Pro Cultura (2.00%: 9365.20), Iva Compras Gravadas (15.00%: 13345.40), Estampilla Pro-Hospital (1.00%: 4682.60), Tasa Pro Deporte y Recreación (2.00%: 9365.20), Estampilla pro-juaticia familiar (2.00%: 9365.20)
CS-012-2026,CE N° 00270,22/05/2026,ACUAMBIENTE S.A.S,2.3.2.02.01.003,1529999,166500.00,1363499.00,Industria y comercio ICA (0.60%: 7714.30), Estampilla Pro Cultura (2.00%: 25714.30), Iva Compras Gravadas (15.00%: 36642.80), Estampilla Pro-Hospital (1.00%: 12857.10), Retención Compras 2.5 (2.50%: 32142.90), Tasa Pro Deporte y Recreación (2.00%: 25714.30), Estampilla pro-juaticia familiar (2.00%: 25714.30)
CS-012-2026,CE N° 00302,03/06/2026,ACUAMBIENTE S.A.S,2.3.2.02.01.003,200991,17650.10,183340.90,Industria y comercio ICA (0.60%: 1013.40), Estampilla Pro Cultura (2.00%: 3378.00), Iva Compras Gravadas (15.00%: 4813.70), Estampilla Pro-Hospital (1.00%: 1689.00), Tasa Pro Deporte y Recreación (2.00%: 3378.00), Estampilla pro-juaticia familiar (2.00%: 3378.00)
CS-012-2026,CE N° 00303,03/06/2026,ACUAMBIENTE S.A.S,2.3.2.02.01.003,6585336,716639.50,5868696.50,Industria y comercio ICA (0.60%: 33203.40), Estampilla Pro Cultura (2.00%: 110677.90), Iva Compras Gravadas (15.00%: 157716.00), Estampilla Pro-Hospital (1.00%: 55339.00), Retención Compras 2.5 (2.50%: 138347.40), Tasa Pro Deporte y Recreación (2.00%: 110677.90), Estampilla pro-juaticia familiar (2.00%: 110677.90)
CS-012-2026,CE N° 00314,10/06/2026,ACUAMBIENTE S.A.S,2.3.2.02.01.003,2715009,295456.90,2419552.10,Industria y comercio ICA (0.60%: 13689.10), Estampilla Pro Cultura (2.00%: 45630.40), Iva Compras Gravadas (15.00%: 65023.40), Estampilla Pro-Hospital (1.00%: 22815.20), Retención Compras 2.5 (2.50%: 57038.00), Tasa Pro Deporte y Recreación (2.00%: 45630.40), Estampilla pro-juaticia familiar (2.00%: 45630.40)
CS-012-2026,CE N° 00338,23/06/2026,ACUAMBIENTE S.A.S,2.3.2.02.01.003,940000,71440.00,868560.00,Industria y comercio ICA (0.60%: 5640.00), Estampilla Pro Cultura (2.00%: 18800.00), Estampilla Pro-Hospital (1.00%: 9400.00), Tasa Pro Deporte y Recreación (2.00%: 18800.00), Estampilla pro-juaticia familiar (2.00%: 18800.00)
CS-012-2026,CE N° 00364,06/07/2026,ACUAMBIENTE S.A.S,2.3.2.02.01.003,3272238,356096.50,2916141.50,Industria y comercio ICA (0.60%: 16498.70), Estampilla Pro Cultura (2.00%: 54995.60), Iva Compras Gravadas (15.00%: 78368.70), Estampilla Pro-Hospital (1.00%: 27497.80), Retención Compras 2.5 (2.50%: 68744.50), Tasa Pro Deporte y Recreación (2.00%: 54995.60), Estampilla pro-juaticia familiar (2.00%: 54995.60)
CS-012-2026,CE N° 00380,09/07/2026,ACUAMBIENTE S.A.S,2.3.2.02.01.003,6646281,723271.90,5923009.10,Industria y comercio ICA (0.60%: 33510.70), Estampilla Pro Cultura (2.00%: 111702.20), Iva Compras Gravadas (15.00%: 159175.70), Estampilla Pro-Hospital (1.00%: 55851.10), Retención Compras 2.5 (2.50%: 139627.80), Tasa Pro Deporte y Recreación (2.00%: 111702.20), Estampilla pro-juaticia familiar (2.00%: 111702.20)
CS-012-2026,CE N° 00381,09/07/2026,ACUAMBIENTE S.A.S,2.3.2.02.01.003,8347126,908363.60,7438762.40,Industria y comercio ICA (0.60%: 42086.40), Estampilla Pro Cultura (2.00%: 140287.80), Iva Compras Gravadas (15.00%: 199910.10), Estampilla Pro-Hospital (1.00%: 70143.90), Retención Compras 2.5 (2.50%: 175359.80), Tasa Pro Deporte y Recreación (2.00%: 140287.80), Estampilla pro-juaticia familiar (2.00%: 140287.80)
CS-014-2026,CE N° 00038,30/01/2026,ACUATUBOS LTDA.,2.3.2.02.02.005,39377.46,3259.40,36118.06,Estampilla Pro Cultura (2.00%: 661.80), Iva Compras Gravadas (15.00%: 943.10), Estampilla Pro-Hospital (1.00%: 330.90), Tasa Pro Deporte y Recreación (2.00%: 661.80), Estampilla pro-juaticia familiar (2.00%: 661.80)
CS-014-2026,CE N° 00039,30/01/2026,ACUATUBOS LTDA.,2.3.2.02.02.005,2920827,241766.00,2679061.00,Estampilla Pro Cultura (2.00%: 49089.50), Iva Compras Gravadas (15.00%: 69952.70), Estampilla Pro-Hospital (1.00%: 24544.80), Tasa Pro Deporte y Recreación (2.00%: 49089.50), Estampilla pro-juaticia familiar (2.00%: 49089.50)
CS-014-2026,CE N° 00074,09/02/2026,ACUATUBOS LTDA.,2.3.2.02.02.005,1258435,104164.60,1154270.40,Estampilla Pro Cultura (2.00%: 21150.20), Iva Compras Gravadas (15.00%: 30138.90), Estampilla Pro-Hospital (1.00%: 10575.10), Tasa Pro Deporte y Recreación (2.00%: 21150.20), Estampilla pro-juaticia familiar (2.00%: 21150.20)
CS-014-2026,CE N° 00098,25/02/2026,ACUATUBOS LTDA.,2.3.2.02.02.005,3937558.40,325923.80,3611634.60,Estampilla Pro Cultura (2.00%: 66177.40), Iva Compras Gravadas (15.00%: 94302.90), Estampilla Pro-Hospital (1.00%: 33088.70), Tasa Pro Deporte y Recreación (2.00%: 66177.40), Estampilla pro-juaticia familiar (2.00%: 66177.40)
CS-014-2026,CE N° 00133,05/03/2026,ACUATUBOS LTDA.,2.3.2.02.02.005,22685725,1877768.00,20807957.00,Estampilla Pro Cultura (2.00%: 381272.70), Iva Compras Gravadas (15.00%: 543313.50), Estampilla Pro-Hospital (1.00%: 190636.40), Tasa Pro Deporte y Recreación (2.00%: 381272.70), Estampilla pro-juaticia familiar (2.00%: 381272.70)
CS-014-2026,CE N° 00134,05/03/2026,ACUATUBOS LTDA.,2.3.2.02.02.005,3324619,275189.00,3049430.00,Estampilla Pro Cultura (2.00%: 55875.90), Iva Compras Gravadas (15.00%: 79623.30), Estampilla Pro-Hospital (1.00%: 27938.00), Tasa Pro Deporte y Recreación (2.00%: 55875.90), Estampilla pro-juaticia familiar (2.00%: 55875.90)
CS-014-2026,CE N° 00248,08/05/2026,ACUATUBOS LTDA.,2.3.2.02.02.005,6416174,531086.80,5885087.20,Estampilla Pro Cultura (2.00%: 107834.90), Iva Compras Gravadas (15.00%: 153664.70), Estampilla Pro-Hospital (1.00%: 53917.40), Tasa Pro Deporte y Recreación (2.00%: 107834.90), Estampilla pro-juaticia familiar (2.00%: 107834.90)
CS-014-2026,CE N° 00249,08/05/2026,ACUATUBOS LTDA.,2.3.2.02.02.005,1101536,91177.60,1010358.40,Estampilla Pro Cultura (2.00%: 18513.20), Iva Compras Gravadas (15.00%: 26381.40), Estampilla Pro-Hospital (1.00%: 9256.60), Tasa Pro Deporte y Recreación (2.00%: 18513.20), Estampilla pro-juaticia familiar (2.00%: 18513.20)
CS-014-2026,CE N° 00250,08/05/2026,ACUATUBOS LTDA.,2.3.2.02.02.005,275588,22811.20,252776.80,Estampilla Pro Cultura (2.00%: 4631.70), Iva Compras Gravadas (15.00%: 6600.20), Estampilla Pro-Hospital (1.00%: 2315.90), Tasa Pro Deporte y Recreación (2.00%: 4631.70), Estampilla pro-juaticia familiar (2.00%: 4631.70)
CS-014-2026,CE N° 00251,08/05/2026,ACUATUBOS LTDA.,2.3.2.02.02.005,418833,34668.00,384165.00,Estampilla Pro Cultura (2.00%: 7039.20), Iva Compras Gravadas (15.00%: 10030.80), Estampilla Pro-Hospital (1.00%: 3519.60), Tasa Pro Deporte y Recreación (2.00%: 7039.20), Estampilla pro-juaticia familiar (2.00%: 7039.20)
CS-014-2026,CE N° 00252,08/05/2026,ACUATUBOS LTDA.,2.3.2.02.02.005,999477,82729.70,916747.30,Estampilla Pro Cultura (2.00%: 16797.90), Iva Compras Gravadas (15.00%: 23937.00), Estampilla Pro-Hospital (1.00%: 8399.00), Tasa Pro Deporte y Recreación (2.00%: 16797.90), Estampilla pro-juaticia familiar (2.00%: 16797.90)
CS-014-2026,CE N° 00253,08/05/2026,ACUATUBOS LTDA.,2.3.2.02.02.005,2361234,195446.70,2165787.30,Estampilla Pro Cultura (2.00%: 39684.60), Iva Compras Gravadas (15.00%: 56550.60), Estampilla Pro-Hospital (1.00%: 19842.30), Tasa Pro Deporte y Recreación (2.00%: 39684.60), Estampilla pro-juaticia familiar (2.00%: 39684.60)
CS-014-2026,CE N° 00323,19/06/2026,ACUATUBOS LTDA.,2.3.2.02.02.005,2279738,188701.00,2091037.00,Estampilla Pro Cultura (2.00%: 38314.90), Iva Compras Gravadas (15.00%: 54598.80), Estampilla Pro-Hospital (1.00%: 19157.50), Tasa Pro Deporte y Recreación (2.00%: 38314.90), Estampilla pro-juaticia familiar (2.00%: 38314.90)
CS-014-2026,CE N° 00324,19/06/2026,ACUATUBOS LTDA.,2.3.2.02.02.005,195305,16165.90,179139.10,Estampilla Pro Cultura (2.00%: 3282.40), Iva Compras Gravadas (15.00%: 4677.50), Estampilla Pro-Hospital (1.00%: 1641.20), Tasa Pro Deporte y Recreación (2.00%: 3282.40), Estampilla pro-juaticia familiar (2.00%: 3282.40)
CS-014-2026,CE N° 00349,02/07/2026,ACUATUBOS LTDA.,2.3.2.02.02.005,12801068,1059584.20,11741483.80,Estampilla Pro Cultura (2.00%: 215144.00), Iva Compras Gravadas (15.00%: 306580.20), Estampilla Pro-Hospital (1.00%: 107572.00), Tasa Pro Deporte y Recreación (2.00%: 215144.00), Estampilla pro-juaticia familiar (2.00%: 215144.00)
CS-014-2026,CE N° 00372,08/07/2026,ACUATUBOS LTDA.,2.3.2.02.02.005,40622,0.00,40622.00
CS-014-2026,CE N° 00402,04/08/2026,ACUATUBOS LTDA.,2.3.2.02.02.005,11569423,957637.20,10611785.80,Estampilla Pro Cultura (2.00%: 194444.10), Iva Compras Gravadas (15.00%: 277082.90), Estampilla Pro-Hospital (1.00%: 97222.00), Tasa Pro Deporte y Recreación (2.00%: 194444.10), Estampilla pro-juaticia familiar (2.00%: 194444.10)"""

CONTRACT_ALIASES = {
    "029-2026": "CO-029-2026",
    "CPS-021-2026": "CS-021-2026",
}

def parse_date(date_str: str):
    if not date_str or not date_str.strip():
        return None
    date_str = date_str.strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None

def parse_retencion_token(token: str):
    token = token.strip()
    if not token or token.lower() == 'sin retenciones':
        return None
    m = re.match(r'^(.*?)\s*\(([\d\.]+)%\s*:\s*([\d\.]+)\)$', token)
    if not m:
        return None
    concepto = m.group(1).strip()
    pct = float(m.group(2))
    val = float(m.group(3))
    
    # Identificación de estampillas y tasas parafiscales
    c_lower = concepto.lower()
    es_estampilla = any(kw in c_lower for kw in [
        'estampilla', 'cultura', 'hospital', 'justicia', 'juaticia', 'deporte'
    ])
    
    return {
        "concepto": concepto,
        "porcentaje": pct,
        "valor": val,
        "es_estampilla": es_estampilla
    }

def seed_payments_table(db: Session = None) -> int:
    """Seed the pagos_contratos table with the 148 payment vouchers and itemized retenciones."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        # Ensure tables and columns exist
        Base.metadata.create_all(bind=engine)
        
        contracts_map = {c.numero_contrato: c for c in db.query(Contrato).all()}
        contractors_by_name = {c.nombre_o_razon_social.strip().upper(): c for c in db.query(Contratista).all()}

        reader = csv.reader(io.StringIO(RAW_PAYMENTS_DATA.strip()))
        header = next(reader)
        inserted = 0
        updated = 0

        for row in reader:
            if not row or not row[0].strip():
                continue
            raw_code = row[0].strip()
            norm_code = CONTRACT_ALIASES.get(raw_code, raw_code)
            egreso_code = row[1].strip()
            fecha_str = row[2].strip()
            benef_name = row[3].strip()
            rubro = row[4].strip()
            
            try:
                tot_orden = float(row[5] or 0.0)
            except ValueError:
                tot_orden = 0.0
            
            try:
                tot_ret = float(row[6] or 0.0)
            except ValueError:
                tot_ret = 0.0
            
            try:
                tot_pagar = float(row[7] or 0.0)
            except ValueError:
                tot_pagar = 0.0

            # Parse retenciones from trailing columns
            retenciones_items = []
            raw_ret_tokens = []
            for t in row[8:]:
                t_str = t.strip()
                if not t_str:
                    continue
                raw_ret_tokens.append(t_str)
                item = parse_retencion_token(t_str)
                if item:
                    retenciones_items.append(item)

            total_estampillas = sum(item["valor"] for item in retenciones_items if item["es_estampilla"])
            retenciones_raw = ", ".join(raw_ret_tokens) if raw_ret_tokens else "Sin retenciones"

            contract = contracts_map.get(norm_code)
            contrato_id = contract.id if contract else None
            contratista_id = contract.contratista_id if contract else None
            if not contratista_id and benef_name:
                c_match = contractors_by_name.get(benef_name.upper())
                if c_match:
                    contratista_id = c_match.id

            fecha_exp = parse_date(fecha_str)

            # Buscar si ya existe
            existing = db.query(PagoContrato).filter(
                PagoContrato.codigo_contrato == norm_code,
                PagoContrato.codigo_egreso == egreso_code
            ).first()

            if existing:
                existing.fecha_expedicion = fecha_exp or existing.fecha_expedicion
                existing.nombre_beneficiario = benef_name or existing.nombre_beneficiario
                existing.rubro_egreso = rubro or existing.rubro_egreso
                existing.total_orden = tot_orden
                existing.total_retencion = tot_ret
                existing.total_pagar = tot_pagar
                existing.total_estampillas = total_estampillas
                existing.retenciones_detalle = retenciones_items
                existing.retenciones_raw = retenciones_raw
                existing.contrato_id = contrato_id or existing.contrato_id
                existing.contratista_id = contratista_id or existing.contratista_id
                updated += 1
            else:
                pago = PagoContrato(
                    codigo_contrato=norm_code,
                    codigo_egreso=egreso_code,
                    fecha_expedicion=fecha_exp,
                    nombre_beneficiario=benef_name,
                    rubro_egreso=rubro,
                    total_orden=tot_orden,
                    total_retencion=tot_ret,
                    total_pagar=tot_pagar,
                    total_estampillas=total_estampillas,
                    retenciones_detalle=retenciones_items,
                    retenciones_raw=retenciones_raw,
                    contrato_id=contrato_id,
                    contratista_id=contratista_id,
                    vigencia=2026,
                    observaciones="Carga con desglose de retenciones y estampillas"
                )
                db.add(pago)
                inserted += 1

        db.commit()
        logger.info(f"Seeding completado con éxito: {inserted} insertados, {updated} actualizados con retenciones y estampillas.")
        return inserted + updated
    except Exception as e:
        db.rollback()
        logger.error(f"Error en seed_payments_table: {e}")
        raise e
    finally:
        if close_db:
            db.close()

if __name__ == "__main__":
    count = seed_payments_table()
    print(f"Seed finalizado. Total registros sincronizados con retenciones: {count}")
