import { useState } from "react";

function Login({ onLoginSuccess }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      const res = await fetch("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password })
      });
      const data = await res.json();
      if (!res.ok || data.ok !== true) {
        throw new Error("Credenciales incorrectas");
      }
      // Login exitoso: el backend ha establecido las cookies JWT
      onLoginSuccess();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <h2>Iniciar sesión</h2>
      {error && <p style={{color:'red'}}>{error}</p>}
      <div>
        <label>Email:</label>
        <input 
          type="email" 
          value={email} 
          onChange={e=> setEmail(e.target.value)} 
          required 
        />
      </div>
      <div>
        <label>Contraseña:</label>
        <input 
          type="password" 
          value={password} 
          onChange={e=> setPassword(e.target.value)} 
          required 
        />
      </div>
      <button type="submit">Entrar</button>
    </form>
  );
}

export default Login;

