export const LOGIN_BACKGROUND_NONE = "none";
export const LOGIN_BACKGROUND_CUSTOM = "custom";

export interface LoginBackgroundOption {
  id: string;
  src: string;
  thumbnail: string;
  label: string;
}

export const LOGIN_BACKGROUND_OPTIONS: LoginBackgroundOption[] = [
  {
    id: LOGIN_BACKGROUND_NONE,
    src: "",
    thumbnail: "",
    label: "None",
  },
  {
    id: "foundations",
    src: "/login-backgrounds/foundations-bg.jpg",
    thumbnail: "/login-backgrounds/thumbnails/foundations-bg.jpg",
    label: "Foundations",
  },
  {
    id: "magellan",
    src: "/login-backgrounds/magellan-cover.jpg",
    thumbnail: "/login-backgrounds/thumbnails/magellan-cover.jpg",
    label: "Magellan",
  },
  {
    id: "clouds",
    src: "/chat-backgrounds/clouds.jpg",
    thumbnail: "/chat-backgrounds/thumbnails/clouds.jpg",
    label: "Clouds",
  },
  {
    id: "hills",
    src: "/chat-backgrounds/hills.jpg",
    thumbnail: "/chat-backgrounds/thumbnails/hills.jpg",
    label: "Hills",
  },
  {
    id: "plant",
    src: "/chat-backgrounds/plant.jpg",
    thumbnail: "/chat-backgrounds/thumbnails/plant.jpg",
    label: "Plants",
  },
  {
    id: "mountains",
    src: "/chat-backgrounds/mountains.jpg",
    thumbnail: "/chat-backgrounds/thumbnails/mountains.jpg",
    label: "Mountains",
  },
  {
    id: "night",
    src: "/chat-backgrounds/night.jpg",
    thumbnail: "/chat-backgrounds/thumbnails/night.jpg",
    label: "Night",
  },
];

export function getLoginBackgroundOptionByUrl(
  url: string | null | undefined
): LoginBackgroundOption | undefined {
  if (!url) return LOGIN_BACKGROUND_OPTIONS[0];
  return LOGIN_BACKGROUND_OPTIONS.find((option) => option.src === url);
}
