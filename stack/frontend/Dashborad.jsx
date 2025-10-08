import { useState } from "react";

function Dashboard() {
  const [wgMsg, setWgMsg] = useState("");

  const startWireGuard = async () => {
    setWgMsg("");
    try {
      const res = await fetch("/api/wireguard/start", { method: "POST" });
      if (!res.ok) throw new Error("Error al activar WireGuard");
      setWgMsg("WireGuard activado correctamente.");
    } catch (err) {
      setWgMsg(err.message);
    }
  };

  const downloadConfig = async () => {
    try {
      // 1. Crear peer (nombre fijo "cliente1" por ejemplo)
      const res = await fetch("/peers", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: "cliente1" })
      });
      if (!res.ok) throw new Error("Error al crear peer");
      const peer = await res.json();
      const peerId = peer.id;
      // 2. Solicitar archivo de configuración
      const resConf = await fetch(`/peers/${peerId}/config`);
      if (!resConf.ok) throw new Error("Error al obtener configuración");
      const confText = await resConf.text();
      // 3. Forzar descarga del .conf
      const blob = new Blob([confText], { type: "text/plain" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `AutoVPN-${peer.name}.conf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert(err.message);
    }
  };

  return (
    <div>
      <h2>Panel de Control</h2>
      <button onClick={startWireGuard}>Activar WireGuard</button>
      <button onClick={downloadConfig}>Descargar configuración</button>
      {wgMsg && <p>{wgMsg}</p>}
    </div>
  );
}

export default Dashboard;

