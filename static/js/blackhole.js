const canvas = document.getElementById('blackholeCanvas');
const ctx = canvas.getContext('2d');
canvas.width = window.innerWidth;
canvas.height = window.innerHeight;

let particles = [];

class Particle {
  constructor(x, y) {
    this.x = x;
    this.y = y;
    this.size = Math.random() * 5 + 1;
    this.speedX = (Math.random() - 0.5) * 2;
    this.speedY = (Math.random() - 0.5) * 2;
    this.color = 'white';
  }

  update() {
    this.size -= 0.05;
    if (this.size < 0) {
      this.x = (canvas.width / 2) + (Math.random() * 200 - 100);
      this.y = (canvas.height / 2) + (Math.random() * 200 - 100);
      this.size = Math.random() * 5 + 1;
      this.speedX = (Math.random() - 0.5) * 2;
      this.speedY = (Math.random() - 0.5) * 2;
    }
    this.x -= this.speedX;
    this.y -= this.speedY;
  }

  draw() {
    ctx.fillStyle = this.color;
    ctx.beginPath();
    ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
    ctx.fill();
  }
}

function init() {
  for (let i = 0; i < 150; i++) {
    particles.push(new Particle(
      (canvas.width / 2) + (Math.random() * 200 - 100),
      (canvas.height / 2) + (Math.random() * 200 - 100)
    ));
  }
}

function animate() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  for (let i = 0; i < particles.length; i++) {
    particles[i].update();
    particles[i].draw();
  }
  requestAnimationFrame(animate);
}

init();
animate();
