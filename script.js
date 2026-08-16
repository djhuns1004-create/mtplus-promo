document.querySelectorAll(".ripple").forEach(function(el){
  el.addEventListener("click", function(e){
    const rect = el.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height);
    const span = document.createElement("span");
    span.className = "ripple-effect";
    span.style.width = size + "px";
    span.style.height = size + "px";
    span.style.left = (e.clientX - rect.left - size/2) + "px";
    span.style.top = (e.clientY - rect.top - size/2) + "px";
    const old = el.querySelector(".ripple-effect");
    if(old) old.remove();
    el.appendChild(span);
    setTimeout(()=>span.remove(), 600);
  });
});
