// src/App.jsx
import React, { useEffect, useMemo, useRef, useState } from "react";

/** Paleta y estilos base */
const COLORS = {
  text: "#ffffff",
  subtext: "#ffffff",
  orange: "#ff7a18",     // naranja tecnológico
  border: "#ffffff",     // perfil de caja
  inputBg: "transparent",
  inputBorder: "#404757",
  inputText: "#e6edf3",
  inputPlaceholder: "#9aa4b2",
};

const baseInput = {
  width: "100%",
  maxWidth: "100%",
  boxSizing: "border-box",
  padding: "10px 12px",
  borderRadius: 8,
  border: `1px solid ${COLORS.inputBorder}`,
  background: COLORS.inputBg,
  color: COLORS.inputText,
  outline: "none",
};

const baseTextarea = {
  ...baseInput,
  fontFamily: "monospace",
  minHeight: 112,
};

const rowStyle = {
  display: "grid",
  gridTemplateColumns: "260px 1fr",
  gap: 12,
  alignItems: "center",
  marginBottom: 10,
};

const sectionStyle = {
  border: `1px solid ${COLORS.border}`, // perfil en blanco
  borderRadius: 12,
  padding: 16,
  marginTop: 16,
  background: "transparent",           // interior transparente (fondo oscuro visible)
};

const sectionTitleStyle = {
  marginTop: 0,
  marginBottom: 12,
  color: COLORS.orange,                // títulos de cajas en naranja
  fontWeight: 700,
};

/** Utilidades */
function b64Random(bytes = 48) {
  const arr = new Uint8Array(bytes);
  crypto.getRandomValues(arr);
  let str = String.fromCharCode(...arr);
  return btoa(str).replace(/\+/g, "-").replace(/\//g, "_");
}
async function readFileAsText(file) {
  return new Promise((res, rej) => {
    const r = new FileReader();
    r.onload = () => res(r.result);
    r.onerror = rej;
    r.readAsText(file);
  });
}
function isEmail(v) { return /^[^@]+@[^@]+\.[^@]+$/.test(v); }
function pwStrength(pw) {
  let s = 0;
  if (pw.length >= 8) s++;
  if (/[A-Z]/.test(pw)) s++;
  if (/[a-z]/.test(pw)) s++;
  if (/\d/.test(pw)) s++;
  if (/[^A-Za-z0-9]/.test(pw)) s++;
  return s;
}

export default function App() {
  const [step, setStep] = useState(1);
  const [installDone, setInstallDone] = useState(false);

  // Destino
  const [serverIp, setServerIp] = useState("");
  const [sshUser, setSshUser] = useState("ubuntu");
  const [sshPort, setSshPort] = useState(22);

  // Método de autenticación SSH
  const [authMethod, setAuthMethod] = useState("password"); // 'password' | 'pem'
  const usingPassword = authMethod === "password";
  const usingPem = authMethod === "pem";

  // Credenciales SSH
  const [sshPassword, setSshPassword] = useState("");
  const [pemText, setPemText] = useState("");
  const [pemFileName, setPemFileName] = useState("");

  // Admin inicial
  const [adminEmail, setAdminEmail] = useState("");
  const [adminPassword, setAdminPassword] = useState("");
  const [adminPassword2, setAdminPassword2] = useState("");
  const [showPw, setShowPw] = useState(false);

  // Parámetros stack
  const [useInternalTLS, setUseInternalTLS] = useState(true);
  const [wgPort, setWgPort] = useState(51820);
  const [wgSubnet, setWgSubnet] = useState("10.13.13.0/24");
  const [wgDNS, setWgDNS] = useState("1.1.1.1");
  const [timezone, setTimezone] = useState("Europe/Madrid");
  const [jwtSecret, setJwtSecret] = useState(() => b64Random(48));
  const wgPublicHost = useMemo(() => serverIp || "", [serverIp]);

  // Transporte (auto / manual + udp2raw extra)
  const [transport, setTransport] = useState({
    mode: "auto",                 // "auto" | "manual"
    profile: "WG_UDP_51820",      // usado solo si mode === "manual"
    udp2raw: {
      enabled: false,             // true si profile === "WG_UDP2RAW_443"
      password: "",               // opcional
      mtu: ""                     // opcional
    }
  });

  // Estado instalación / logs
  const [checkingSSH, setCheckingSSH] = useState(false);
  const [sshOk, setSshOk] = useState(null);
  const [configOk, setConfigOk] = useState(null);
  const [installing, setInstalling] = useState(false);
  const [logs, setLogs] = useState("");
  const [serverUrl, setServerUrl] = useState("");
  const logsRef = useRef(null);
  const esRef = useRef(null);

  useEffect(() => {
    const el = logsRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [logs]);

  function appendLog(line) {
    setLogs(prev => (prev ? `${prev}\n${line}` : line));
  }

  async function handlePemFile(e) {
    const f = e.target.files?.[0];
    if (!f) return;
    setPemFileName(f.name);
    const txt = await readFileAsText(f);
    setPemText(txt);
  }

  // === PROBAR SSH (password o PEM) ===
  async function testSSH() {
    setCheckingSSH(true);
    setSshOk(null);
    try {
      const payload = {
        elastic_ip: serverIp.trim(),
        user: sshUser.trim() || "ubuntu",
        ssh_port: Number(sshPort) || 22,
      };
      if (usingPem) {
        if (!pemText) throw new Error("Falta la clave .pem");
        payload.pem = pemText;
      } else {
        if (!sshPassword) throw new Error("Falta la contraseña SSH");
        payload.ssh_password = sshPassword;
      }

      const res = await fetch("/install/check-ssh", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Fallo SSH");
      setSshOk(true);
    } catch (e) {
      console.error(e);
      setSshOk(false);
    } finally {
      setCheckingSSH(false);
    }
  }

  // Validaciones
  const adminEmailOk = isEmail(adminEmail);
  const pwOk = adminPassword.length >= 8 && adminPassword === adminPassword2;

  const hasSshCreds =
    (usingPem && !!pemText) ||
    (usingPassword && !!sshPassword);

  const canTestSSH =
    usingPem
      ? (serverIp && sshUser && pemText && sshPort)
      : (serverIp && sshUser && sshPassword && sshPort);

  const canProceedStep1 =
    serverIp && sshUser && hasSshCreds && adminEmailOk && pwOk && sshPort;

  // === Guardar config ===
  
  async function writeConfig() {
	  if (!canProceedStep1) {
		alert("Revisa datos: IP, usuario, puerto, credencial SSH (password o .pem) y credenciales admin.");
		return;
	  }
	  setConfigOk(null);

	  try {
		// Normalización
		const ip = (serverIp || "").trim();
		const user = (sshUser || "ubuntu").trim();

		const p = Number(sshPort);
		const portSSH = Number.isFinite(p) && p > 0 ? p : 22;

		const wgP = Number(wgPort);
		const wgPortSafe = Number.isFinite(wgP) && wgP > 0 ? wgP : 51820;

		const payload = {
		  ssh: {
			elastic_ip: ip,
			user,
			ssh_port: portSSH,
		  },
		  vars: {
			use_internal_tls: !!useInternalTLS,
			wg_public_host: (wgPublicHost || ip).trim(),
			wg_port: wgPortSafe,
			wg_subnet: (wgSubnet || "").trim(),
			wg_dns: (wgDNS || "").trim(),
			jwt_secret: (jwtSecret || "").trim(),
			timezone: (timezone || "").trim(),
			admin_email: (adminEmail || "").trim(),
			admin_password: (adminPassword || "").trim(),
		  },
		  // No enviar campos extra si la API no los define (p. ej. transport)
		};

		// Sólo una credencial SSH
		if (usingPem) {
		  const key = pemText || "";
		  if (!key) throw new Error("La clave PEM está vacía.");
		  payload.ssh.pem = key;
		} else {
		  const pass = (sshPassword || "").trim();
		  if (!pass) throw new Error("La contraseña SSH está vacía.");
		  payload.ssh.ssh_password = pass;
		}

		// Validación mínima local
		const required = [
		  payload.ssh.elastic_ip,
		  payload.vars.wg_public_host,
		  payload.vars.wg_subnet,
		  payload.vars.wg_dns,
		  payload.vars.jwt_secret,
		  payload.vars.timezone,
		  payload.vars.admin_email,
		  payload.vars.admin_password,
		];
		if (required.some(v => !v)) {
		  throw new Error("Faltan campos requeridos en la configuración.");
		}

		const res = await fetch("/install/config", {
		  method: "POST",
		  headers: { "Content-Type": "application/json" },
		  body: JSON.stringify(payload),
		});

		const text = await res.text();
		let data = {};
		try { data = text ? JSON.parse(text) : {}; } catch {}

		if (!res.ok || data.ok === false) {
		  const detail = data.detail ? JSON.stringify(data.detail) : text || `HTTP ${res.status}`;
		  throw new Error(detail);
		}

		setConfigOk(true);
		setAdminPassword(""); setAdminPassword2("");
		setStep(3);
	  } catch (e) {
		console.error(e);
		const msg = e instanceof Error ? e.message : String(e);
		alert(`No se pudo guardar la configuración:\n${msg}`);
		setConfigOk(false);
	  }
  }


  // === Ejecutar instalación (SSE logs) ===
  async function runInstall() {
    setInstalling(true);
    setLogs("");
    setServerUrl("");
    setInstallDone(false);
    try {
      const ssh = {
        elastic_ip: serverIp.trim(),
        user: sshUser.trim() || "ubuntu",
        ssh_port: Number(sshPort) || 22,
      };
      if (usingPem) ssh.pem = pemText;
      else ssh.ssh_password = sshPassword;

      const res = await fetch("/install/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ssh,
          vars: {
            use_internal_tls: useInternalTLS,
            wg_public_host: wgPublicHost,
            wg_port: Number(wgPort),
            wg_subnet: wgSubnet,
            wg_dns: wgDNS,
            jwt_secret: jwtSecret,
            timezone,
            admin_email: adminEmail.trim(),
            admin_password: adminPassword || undefined,
          },
          //transport,
        }),
      });
      const data = await res.json();
      if (!res.ok || !data?.run_id) throw new Error(data?.detail || "No se obtuvo run_id");

      const es = new EventSource(`/install/logs/${data.run_id}`);
      esRef.current = es;
      es.addEventListener("message", ev => { if (ev?.data) appendLog(ev.data); });
      es.addEventListener("info", ev => { if (ev?.data) appendLog(`[INFO] ${ev.data}`); });
      es.addEventListener("error", () => { appendLog("[ERROR] Error en el stream de logs"); });
      es.addEventListener("done", ev => {
        const url = ev?.data?.trim();
        if (url) setServerUrl(url);
        appendLog(`[DONE] Instalación terminada. Panel: ${url || "(desconocido)"}`);
        es.close();
        setInstalling(false);
        setInstallDone(true);
        setAdminPassword(""); setAdminPassword2("");
      });
    } catch (e) {
      console.error(e);
      appendLog(`[ERROR] ${e.message}`);
      setInstalling(false);
      setAdminPassword(""); setAdminPassword2("");
    }
  }

  return (
    <div style={{ maxWidth: 880, margin: "2rem auto", fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif", color: COLORS.text }}>
      {/* Título principal en naranja */}
      <h1 style={{ marginBottom: 8, color: COLORS.orange }}>AutoVPN – Instalación asistida</h1>

      {/* Subtítulo en blanco */}
      <p style={{ marginTop: 0, color: COLORS.subtext }}>
        Fase 1: prepara tu servidor con Ansible (deploy & stack). Después abrirás el panel del servidor (Fase 2).
      </p>

      {/* Paso 1 */}
      {step === 1 && (
        <div>
          {/* Sección 1: Credenciales y autenticación */}
          <section style={sectionStyle}>
            <h2 style={sectionTitleStyle}>Credenciales y autenticación</h2>

            <div style={rowStyle}>
              <label>IP/Elastic IP del servidor</label>
              <input
                placeholder="1.2.3.4 o host.docker.internal"
                value={serverIp}
                onChange={(e) => setServerIp(e.target.value.trim())}
                style={baseInput}
              />
            </div>

            <div style={rowStyle}>
              <label>Puerto SSH</label>
              <input
                type="number"
                min={1}
                max={65535}
                placeholder="22"
                value={sshPort}
                onChange={(e) => setSshPort(e.target.value ? Number(e.target.value) : "")}
                style={baseInput}
                inputMode="numeric"
              />
            </div>

            <div style={rowStyle}>
              <label>Método de autenticación SSH</label>
              <div style={{ display: "flex", gap: 16 }}>
                <label style={{ display: "flex", gap: 8, alignItems: "center", cursor: "pointer" }}>
                  <input
                    type="radio"
                    name="authMethod"
                    value="password"
                    checked={authMethod === "password"}
                    onChange={() => setAuthMethod("password")}
                  />
                  <span>Usuario y contraseña</span>
                </label>
                <label style={{ display: "flex", gap: 8, alignItems: "center", cursor: "pointer" }}>
                  <input
                    type="radio"
                    name="authMethod"
                    value="pem"
                    checked={authMethod === "pem"}
                    onChange={() => setAuthMethod("pem")}
                  />
                  <span>Clave SSH .pem</span>
                </label>
              </div>
            </div>

            {/* Sub-bloque: Usuario/Contraseña */}
            {usingPassword && (
              <>
                <div style={rowStyle}>
                  <label>Usuario</label>
                  <input
                    placeholder="ubuntu"
                    value={sshUser}
                    onChange={(e) => setSshUser(e.target.value)}
                    style={baseInput}
                  />
                </div>
                <div style={rowStyle}>
                  <label>Contraseña</label>
                  <input
                    type="password"
                    placeholder="••••••••"
                    value={sshPassword}
                    onChange={(e) => setSshPassword(e.target.value)}
                    style={baseInput}
                  />
                </div>
              </>
            )}

            {/* Sub-bloque: PEM */}
            {usingPem && (
              <>
                <div style={rowStyle}>
                  <label>Usuario</label>
                  <input
                    placeholder="ubuntu"
                    value={sshUser}
                    onChange={(e) => setSshUser(e.target.value)}
                    style={baseInput}
                  />
                </div>
                <div style={rowStyle}>
                  <label>Seleccionar archivo</label>
                  <div>
                    <input type="file" accept=".pem" onChange={handlePemFile} />
                    {pemFileName ? <div style={{ marginTop: 6 }}><code>{pemFileName}</code></div> : null}
                  </div>
                </div>
                <div style={rowStyle}>
                  <label>Clave SSH (.pem)</label>
                  <textarea
                    rows={6}
                    placeholder="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----"
                    value={pemText}
                    onChange={(e) => setPemText(e.target.value)}
                    style={baseTextarea}
                  />
                </div>
              </>
            )}
          </section>

          {/* Sección 2: Usuario administrador inicial */}
          <section style={sectionStyle}>
            <h2 style={sectionTitleStyle}>Usuario administrador inicial</h2>

            <div style={rowStyle}>
              <label>Email</label>
              <input
                placeholder="admin@autovpn.local"
                value={adminEmail}
                onChange={(e) => setAdminEmail(e.target.value)}
                style={baseInput}
              />
            </div>
            {!isEmail(adminEmail) && adminEmail && (
              <div style={{ margin: "4px 0 10px 260px", color: "#ffb3b3" }}>Formato de email inválido</div>
            )}

            <div style={rowStyle}>
              <label>Contraseña</label>
              <input
                type={showPw ? "text" : "password"}
                value={adminPassword}
                onChange={(e) => setAdminPassword(e.target.value)}
                style={baseInput}
              />
            </div>
            {adminPassword && (
              <div style={{ margin: "4px 0 10px 260px", color: pwStrength(adminPassword) >= 4 ? "#52ffa8" : "#ffcc66" }}>
                Fortaleza: {pwStrength(adminPassword)} / 5
              </div>
            )}

            <div style={rowStyle}>
              <label>Repetir contraseña</label>
              <input
                type={showPw ? "text" : "password"}
                value={adminPassword2}
                onChange={(e) => setAdminPassword2(e.target.value)}
                style={baseInput}
              />
            </div>
            {adminPassword2 && adminPassword2 !== adminPassword && (
              <div style={{ margin: "4px 0 10px 260px", color: "#ffb3b3" }}>No coincide</div>
            )}

            {/* Mostrar contraseña (al final de la caja, alineado a la izquierda) */}
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 8 }}>
              <input
                id="showPw"
                type="checkbox"
                checked={showPw}
                onChange={(e) => setShowPw(e.target.checked)}
              />
              <label htmlFor="showPw" style={{ cursor: "pointer" }}>Mostrar contraseña</label>
            </div>
          </section>

          {/* Sección 3: Parámetros de despliegue */}
          <section style={sectionStyle}>
            <h2 style={sectionTitleStyle}>Parámetros de despliegue</h2>

            {/* Perfil de transporte */}
            <div style={{border:'1px solid #444', borderRadius:8, padding:16, marginTop:16}}>
              <h3 style={{marginTop:0, color: COLORS.orange}}>Perfil de transporte</h3>

              <label style={{display:'block', marginBottom:8}}>
                <input
                  type="radio"
                  name="transportMode"
                  checked={transport.mode === "auto"}
                  onChange={() => setTransport({ ...transport, mode:"auto" })}
                />{" "}
                Auto-detección (recomendado)
              </label>

              <label style={{display:'block', marginBottom:8}}>
                <input
                  type="radio"
                  name="transportMode"
                  checked={transport.mode === "manual"}
                  onChange={() => setTransport({ ...transport, mode:"manual" })}
                />{" "}
                Manual
              </label>

              {transport.mode === "manual" && (
                <div style={{display:'grid', gap:8, gridTemplateColumns:'1fr 1fr'}}>
                  <label>Perfil
                    <select
                      style={{width:'100%'}}
                      value={transport.profile}
                      onChange={(e) => {
                        const profile = e.target.value;
                        setTransport(t => ({
                          ...t,
                          profile,
                          udp2raw: {
                            ...t.udp2raw,
                            enabled: profile === "WG_UDP2RAW_443"
                          }
                        }))
                      }}
                    >
                      <option value="WG_UDP_51820">WG/UDP 51820 (por defecto)</option>
                      <option value="WG_UDP_443">WG/UDP 443 (simula QUIC)</option>
                      <option value="WG_UDP2RAW_443">WG encapsulado (udp2raw/443)</option>
                    </select>
                  </label>

                  {/* Campos extra si udp2raw */}
                  {transport.profile === "WG_UDP2RAW_443" && (
                    <>
                      <label>Password udp2raw (opcional)
                        <input
                          type="text"
                          value={transport.udp2raw.password}
                          onChange={(e) => setTransport(t => ({
                            ...t,
                            udp2raw: {...t.udp2raw, enabled:true, password: e.target.value}
                          }))}
                          style={{width:'100%'}}
                        />
                      </label>
                      <label>MTU (opcional)
                        <input
                          type="number"
                          min={1100}
                          max={1500}
                          value={transport.udp2raw.mtu}
                          onChange={(e) => setTransport(t => ({
                            ...t,
                            udp2raw: {...t.udp2raw, enabled:true, mtu: e.target.value}
                          }))}
                          style={{width:'100%'}}
                        />
                      </label>
                    </>
                  )}
                </div>
              )}

              <small style={{display:'block', marginTop:8, color:'#aaa'}}>
                En “Auto” el cliente probará: 51820/UDP → 443/UDP → udp2raw/443/TCP.
              </small>
            </div>

            {/* Usar TLS interno (alineado a la izquierda) */}
            <div style={{ display: "flex", alignItems: "center", gap: 8, margin: "12px 0" }}>
              <input
                id="useInternalTLS"
                type="checkbox"
                checked={useInternalTLS}
                onChange={(e) => setUseInternalTLS(e.target.checked)}
              />
              <label htmlFor="useInternalTLS" style={{ cursor: "pointer" }}>Usar TLS interno</label>
            </div>

            <div style={rowStyle}>
              <label>WG Port</label>
              <input value={wgPort} onChange={(e) => setWgPort(e.target.value)} style={baseInput} />
            </div>

            <div style={rowStyle}>
              <label>TimeZone</label>
              <input value={timezone} onChange={(e) => setTimezone(e.target.value)} style={baseInput} />
            </div>

            <div style={rowStyle}>
              <label>WG Subnet</label>
              <input value={wgSubnet} onChange={(e) => setWgSubnet(e.target.value)} style={baseInput} />
            </div>

            <div style={rowStyle}>
              <label>WG DNS</label>
              <input value={wgDNS} onChange={(e) => setWgDNS(e.target.value)} style={baseInput} />
            </div>

            <div style={rowStyle}>
              <label>JWT Secret</label>
              <div style={{ display: "flex", gap: 8, width: "100%" }}>
                <input value={jwtSecret} onChange={(e) => setJwtSecret(e.target.value)} style={baseInput} />
                <button type="button" onClick={() => setJwtSecret(b64Random(48))}>Regenerar</button>
              </div>
            </div>
          </section>

          {/* Acciones */}
          <div style={{ marginTop: 16, display: "flex", gap: 12 }}>
            <button
              onClick={testSSH}
              disabled={!canTestSSH || checkingSSH}
            >
              {checkingSSH ? "Probando SSH..." : "Probar SSH"}
            </button>
            {sshOk === true && <span style={{ color: "#52ffa8" }}>✓ SSH OK</span>}
            {sshOk === false && <span style={{ color: "#ff9aa2" }}>✗ SSH falló</span>}
          </div>

          <div style={{ marginTop: 16, display: "flex", gap: 12 }}>
            <button
              onClick={writeConfig}
	      disabled={!canProceedStep1 || sshOk !== true || (usingPem && !pemText)}
              title={sshOk !== true ? "Primero verifica SSH" : ""}
            >
              Guardar configuración y continuar
            </button>
          </div>
        </div>
      )}

      {/* Paso 2 (instalación) */}
      {step === 3 && (
        <div>
          <h2 style={{ color: COLORS.orange }}>Paso 2 · Ejecutar instalación (Ansible)</h2>
          <p style={{ color: COLORS.subtext }}>
            Se lanzarán los playbooks <code>site-deploy.yml</code> y <code>site-stack.yml</code>. Verás los logs en vivo.
          </p>
          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
            <button onClick={() => setStep(1)} disabled={installing}>« Atrás</button>
            <button onClick={runInstall} disabled={installing}>Instalar ahora</button>
            <button onClick={() => setStep(4)} disabled={!installDone} title={!installDone ? "Espera a que la instalación termine" : ""}>
              Continuar al paso 3
            </button>
          </div>
          <h3 style={{ marginTop: 16, color: COLORS.orange }}>Logs</h3>
          <pre
            ref={logsRef}
            style={{
              whiteSpace: "pre-wrap",
              background: "#0b1020",
              color: "#e6edf3",
              padding: 12,
              borderRadius: 8,
              maxHeight: 360,
              overflow: "auto",
              fontSize: 13,
              border: `1px solid ${COLORS.inputBorder}`,
            }}
          >
            {logs || "Esperando salida..."}
          </pre>
        </div>
      )}

      {/* Paso final */}
      {step === 4 && (
        <div>
          <h2 style={{ color: COLORS.orange }}>Paso 3 · ¡Listo!</h2>
          <p style={{ color: COLORS.subtext }}>
            Abre el panel del servidor (Fase 2: login+2FA, crear dispositivo, descargar .conf/QR).
          </p>
          <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 12 }}>
            <a href={serverUrl || `https://${serverIp}/`} target="_blank" rel="noreferrer">
              <button>Abrir panel del servidor</button>
            </a>
            {useInternalTLS && (
              <small style={{ color: COLORS.subtext }}>
                TLS interno: instala la CA de Caddy para evitar avisos.
              </small>
            )}
          </div>
          <div style={{ marginTop: 16 }}>
            <button onClick={() => { setStep(1); setLogs(""); setServerUrl(""); }}>
              Repetir instalación / otro servidor
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

