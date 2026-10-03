"use client";

/**
 * Mi respaldo: la copia cifrada de los pacientes de cada profesional.
 *
 * Es la misma pantalla que Configuración → Copia de seguridad, pero con
 * lo suyo: los pacientes que ha atendido, su historia clínica y su
 * agenda (ver django-api/apps/common/tenant_backup.py). Solo puede abrir
 * aquí las copias que generó él.
 */

import ClinicBackup from "../../../lib/ClinicBackup";

export default function MiRespaldoPage() {
  return (
    <div>
      <h1 style={{ fontSize: 24, marginBottom: 14 }}>Mi respaldo</h1>
      <ClinicBackup alcance="profesional" />
    </div>
  );
}
