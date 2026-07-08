"use client";

import { useEffect } from "react";
import { currentUser } from "../lib/api";

export default function Home() {
  useEffect(() => {
    window.location.href = currentUser() ? "/panel/" : "/login/";
  }, []);
  return null;
}
