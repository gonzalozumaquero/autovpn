// src/App.jsx
import React, { useState } from "react";
import { genWGKeypair } from "./lib/wg-crypto";


export default function App() {
  const [step, setStep] = useState(1);
  const [serverIp, setServerIp] = useState("");
  const [peerName, setPeerName] = useState("mi-movil");
  const [sshPassword, setSshPassword] = useState("");

  async function generarYDescargarWG() {
    // 1) Generar claves en cliente
    const { privateKey, publicKey } = await genWGKeypair();

    // 2) Solicitar parámetros del servidor
    const res = await fetch("/api/wg/server_params", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
  	peer_name: peerName,
  	peer_public_key: publicKey,
  	server_hint: serverIp,
  	ssh_user: "autovpn",
  	ssh_password: sshPassword || null
	})
    });
    const params = await res.json();

    // 3) Construir conf local
    const conf = `[Interface]
PrivateKey = ${privateKey}
Address = ${params.client_address}
DNS = ${params.dns}

[Peer]
PublicKey = ${params.server_public_key}
Endpoint = ${params.endpoint}
AllowedIPs = ${params.allowed_ips}
`;

    // 4) Descargar archivo
    const blob = new Blob([conf], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `${peerName}.conf`;
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
  }



  return (
    <div style={{ maxWidth: "600px", margin: "2rem auto", fontFamily: "sans-serif" }}>
      <h1>AutoVPN</h1>
      {step === 1 && (
        <div>
          <h2>Paso 1: Servidor destino</h2>
	      <input placeholder="IP del servidor" value={serverIp} onChange={e => setServerIp(e.target.value)} />
              <input placeholder="Nombre del dispositivo" value={peerName} onChange={e => setPeerName(e.target.value)} />
              <input placeholder="Contraseña SSH (opcional)" value={sshPassword} onChange={e => setSshPassword(e.target.value)} />
          <button onClick={() => setStep(2)}>Continuar</button>   
        </div>
      )}
      {step === 2 && (
        <div>
          <h2>Paso 2: Protocolo</h2>
          <select>
            <option>WireGuard</option>
            <option>OpenVPN</option>
          </select>
          <button onClick={() => setStep(1)}>Atrás</button>
          <button onClick={() => setStep(3)}>Continuar</button>
        </div>
      )}
      {step === 3 && (
        <div>
          <h2>Paso 3: Generar configuración</h2>
	  <button onClick={generarYDescargarWG}>Generar y descargar .conf</button>
          <button onClick={() => setStep(2)}>Atrás</button>
        </div>
      )}
    </div>
  );
}



