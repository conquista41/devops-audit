import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: `${API_URL}/api/v1`,
});

// Token'ı her isteğe otomatik ekle
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Token süresi dolmuşsa refresh et
api.interceptors.response.use(
  (res) => res,
  async (error) => {
    if (error.response?.status === 401) {
      const refresh = localStorage.getItem("refresh_token");
      if (refresh) {
        try {
          const { data } = await axios.post(`${API_URL}/api/v1/auth/refresh`, {
            refresh_token: refresh,
          });
          localStorage.setItem("access_token", data.access_token);
          localStorage.setItem("refresh_token", data.refresh_token);
          error.config.headers.Authorization = `Bearer ${data.access_token}`;
          return axios(error.config);
        } catch {
          localStorage.clear();
          window.location.href = "/";
        }
      }
    }
    return Promise.reject(error);
  }
);

// API fonksiyonları
export const authApi = {
  getLoginUrl: () => api.get("/auth/github/login"),
};

export const userApi = {
  getMe: () => api.get("/users/me"),
};

export const scanApi = {
  create: (data: { scan_type: string; target: string; config?: object }) =>
    api.post("/scans/", data),
  list: (limit = 20, offset = 0) =>
    api.get(`/scans/?limit=${limit}&offset=${offset}`),
  get: (id: string) => api.get(`/scans/${id}`),
};
