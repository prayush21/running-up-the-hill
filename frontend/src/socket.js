import { io } from 'socket.io-client';

const URL = import.meta.env.VITE_BACKEND_URL || `http://${window.location.hostname}:8000`;

export const socket = io(URL, {
    autoConnect: false
});
