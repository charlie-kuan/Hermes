module.exports = {
  apps: [
    {
      name: "hermes-backend",
      script: "/root/miniconda3/envs/Hermes/bin/uvicorn",
      args: "app.main:app --host 0.0.0.0 --port 8000 --workers 2",
      cwd: "/root/Project/Hermes",
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
      script: "/usr/bin/serve",
      args: "-s dist -l 4000 --single",
      cwd: "/root/Project/Hermes/frontend",
      interpreter: "none",
      autorestart: true,
      watch: false
    }
  ]
};
