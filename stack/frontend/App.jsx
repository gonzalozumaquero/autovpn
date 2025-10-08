import { useState, useEffect } from "react";
import Login from "./components/Login";
import Dashboard from "./components/Dashboard";

function App() {
  const [loggedIn, setLoggedIn] = useState(false);

  useEffect(() => {
    // Comprobar sesión válida llamando un endpoint protegido (opcional)
    fetch("/api/status").then(res => {
      if (res.ok) setLoggedIn(true);
    });
  }, []);

  return (
    <div className="App">
      { loggedIn 
          ? <Dashboard /> 
          : <Login onLoginSuccess={() => setLoggedIn(true)} />
      }
    </div>
  );
}
export default App;

