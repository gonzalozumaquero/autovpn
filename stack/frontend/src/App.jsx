import { useState, useEffect } from 'react'

function Login({ onLoginSuccess }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    try {
      const res = await fetch('/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      })
      const data = await res.json()
      if (!res.ok || data.ok !== true) throw new Error('Credenciales incorrectas')
      onLoginSuccess()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <form onSubmit={handleSubmit} style={{maxWidth: 360}}>
      <h2>Iniciar sesión</h2>
      {error && <p style={{color:'red'}}>{error}</p>}
      <label>Email</label>
      <input type="email" value={email} onChange={e=>setEmail(e.target.value)} required />
      <label>Contraseña</label>
      <input type="password" value={password} onChange={e=>setPassword(e.target.value)} required />
      <button type="submit">Entrar</button>
    </form>
  )
}

function Dashboard() {
  const [msg, setMsg] = useState('')
  const startWG = async () => {
    setMsg('')
    const r = await fetch('/api/wireguard/start', { method: 'POST' })
    setMsg(r.ok ? 'WireGuard activado' : 'Error al activar WireGuard')
  }
  const downloadConf = async () => {
    // crea peer y descarga .conf
    const r = await fetch('/peers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: 'cliente1' })
    })
    if (!r.ok) { alert('Error creando peer'); return }
    const peer = await r.json()
    const c = await fetch(`/peers/${peer.id}/config`)
    if (!c.ok) { alert('Error obteniendo conf'); return }
    const text = await c.text()
    const blob = new Blob([text], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = `AutoVPN-${peer.name}.conf`
    document.body.appendChild(a); a.click(); a.remove()
    URL.revokeObjectURL(url)
  }
  return (
    <div>
      <h2>Panel</h2>
      <button onClick={startWG}>Activar WireGuard</button>
      <button onClick={downloadConf}>Descargar configuración</button>
      {msg && <p>{msg}</p>}
    </div>
  )
}

export default function App() {
  const [loggedIn, setLoggedIn] = useState(false)
  useEffect(() => { fetch('/api/status').then(r => { if (r.ok) setLoggedIn(true) }) }, [])
  return <div style={{padding: 24}}>{loggedIn ? <Dashboard/> : <Login onLoginSuccess={()=>setLoggedIn(true)} />}</div>
}

