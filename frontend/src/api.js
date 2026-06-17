import axios from "axios";

const api = axios.create({
  baseURL: "/api",
  timeout: 300000,
});

export function createTask(material, docType, projectPath = null, customName = "") {
  const payload = { material, doc_type: docType };
  if (projectPath) {
    payload.project_path = projectPath;
  }
  if (customName) {
    payload.custom_name = customName;
  }
  return api.post("/tasks", payload);
}

export function getTask(taskId) {
  return api.get(`/tasks/${taskId}`);
}

export function listTasks(page = 1, size = 20) {
  return api.get("/tasks", { params: { page, size } });
}

export function deleteTask(taskId) {
  return api.delete(`/tasks/${taskId}`);
}

export function getDownloadUrl(taskId) {
  return `/api/tasks/${taskId}/download`;
}

export function browseFolder() {
  return api.get("/tasks/browse-folder");
}

export function streamTaskProgress(taskId, onProgress, onDone) {
  const url = `/api/tasks/${taskId}/stream`;
  const source = new EventSource(url);

  source.addEventListener("progress", (e) => {
    const data = JSON.parse(e.data);
    onProgress(data);
  });

  source.addEventListener("done", () => {
    source.close();
    if (onDone) onDone();
  });

  source.onerror = () => {
    source.close();
    if (onDone) onDone();
  };

  return () => source.close();
}