"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { getUser, loadStoredAuth, logout } from "@/lib/api";
import styles from "./navbar.module.css";

export default function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<{ username: string; role: string; full_name: string } | null>(null);

  useEffect(() => {
    loadStoredAuth();
    setUser(getUser());
  }, []);

  const handleLogout = () => {
    logout();
    router.push("/");
  };

  const navItems = [
    { label: "Dashboard", href: "/dashboard", icon: "📊" },
    { label: "Evidence Explorer", href: "/evidence", icon: "🗂️" },
    { label: "Datasets & Benchmarks", href: "/datasets", icon: "📦" },
    { label: "Recovery", href: "/recovery", icon: "🔬" },
    { label: "Camera Map", href: "/map", icon: "🗺️" },
    { label: "Audit Logs", href: "/audit", icon: "🛡️" },
  ];

  return (
    <header className={styles.navbar}>
      <Link href="/dashboard" className={styles.brand}>
        <div className={styles.brandLogo}>FV</div>
        <div className={styles.brandText}>
          <span className={styles.brandName}>FORGE-VISION</span>
          <span className={styles.brandSub}>FORENSIC WORKSTATION · SIH150</span>
        </div>
      </Link>

      <nav className={styles.navLinks}>
        {navItems.map((item) => {
          const isActive = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`${styles.navLink} ${isActive ? styles.navLinkActive : ""}`}
            >
              <span>{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className={styles.rightSection}>
        {user ? (
          <div className={styles.userWrap}>
            <span className={`${styles.roleBadge} ${styles[`role_${user.role}`] || ""}`}>
              {user.role}
            </span>
            <span className="mono-sm">{user.full_name || user.username}</span>
            <button onClick={handleLogout} className={styles.logoutBtn} title="Sign Out">
              Sign Out
            </button>
          </div>
        ) : (
          <Link href="/" className={styles.logoutBtn}>Login</Link>
        )}
      </div>
    </header>
  );
}
