// src/App.jsx
import { useState } from "react";

function App() {
  const [step, setStep] = useState(1);

  return (
    <div style={{ maxWidth: "600px", margin: "2rem auto", fontFamily: "sans-serif" }}>
      <h1>AutoVPN</h1>
      {step === 1 && (
        <div>
          <h2>Paso 1: Servidor destino</h2>
          <input placeholder="IP del servidor" />
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
	  <button onClick={() => descargarConf("10.0.2.15")}>Descargar configuración</button>
          <button onClick={() => setStep(2)}>Atrás</button>
        </div>
      )}
    </div>
  );
}


async function descargarConf(serverIp) {
  const body = { server_ip: serverIp, ssh_user: "ubuntu", client_name: "mi-movil" };
  const res = await fetch("/api/wg/config", {
  method: "POST",
  headers: {"Content-Type":"application/json"},
  body: JSON.stringify(body),
  });

  /*const res = await fetch("http://api:8000/wg/config", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify(body),
  });*/

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = "mi-movil.conf";
  document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
}




export default App;

