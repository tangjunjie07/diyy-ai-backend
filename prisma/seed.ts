import { PrismaClient } from '@prisma/client'
import { PrismaPg } from '@prisma/adapter-pg'
import { Pool } from 'pg'
import { config } from 'dotenv'
import bcrypt from 'bcryptjs'

config({ path: '../../.env' })

const connectionString = process.env.DATABASE_URL
const pool = new Pool({ connectionString })
const adapter = new PrismaPg(pool)

const prisma = new PrismaClient({ adapter })

async function main() {
  // Hash password for super admin
  const superAdminPassword = await bcrypt.hash('superadmin123', 10)

  // Create super admin user (no tenant)
  const superAdmin = await prisma.user.upsert({
    where: { email: 'superadmin@example.com' },
    update: {},
    create: {
      email: 'superadmin@example.com',
      name: 'Super Administrator',
      password: superAdminPassword,
      role: 'super_admin',
      tenantId: null, // Super admin has no tenant
    },
  })

  console.log('Seed data created:', { superAdmin })
}

main()
  .catch((e) => {
    console.error(e)
    process.exit(1)
  })
  .finally(async () => {
    await prisma.$disconnect()
  })