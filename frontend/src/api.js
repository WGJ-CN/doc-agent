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
