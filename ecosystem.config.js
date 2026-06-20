module.exports = {
  apps: [
    {
      name: "hermes-backend",
      script: "/opt/miniconda3/bin/conda",
      args: "run -n Hermes uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2",
      cwd: "/path/to/Project_Hermes",   // ← 改成 server 上的實際路徑
      interpreter: "none",
      autorestart: true,
      watch: false,
      max_memory_restart: "1G",
      env: {
        NODE_ENV: "production",
        DEBUG: "false",
        LOG_LEVEL: "INFO"
      }
    },
    {
      name: "hermes-frontend",
      script: "serve",                  // npm install -g serve
      args: "-s dist -l 3000",
      cwd: "/path/to/Project_Hermes/frontend",  // ← 改成實際路徑
      interpreter: "none",
      autorestart: true,
      watch: false
    }
  ]
};
