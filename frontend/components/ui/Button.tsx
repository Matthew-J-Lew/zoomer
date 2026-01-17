import React from "react";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary";
  children: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
  variant = "primary",
  children,
  className = "",
  ...props
}) => {
  const baseStyles =
    "px-6 py-3 rounded-xl font-medium transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-focus text-sm sm:text-base cursor-pointer";

  const variants = {
    primary: "bg-accent text-white hover:bg-accent-hover",
    secondary:
      "bg-surface border border-border text-primary-text hover:bg-surface-subtle",
  };

  return (
    <button
      className={`${baseStyles} ${variants[variant]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
};
